"""V28 local API tests: ephemeral loopback HTTP, no external network."""
import csv
from datetime import datetime, timedelta, timezone
import json
import shutil
import socket
import time
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_api_v28 as v28


class LocalApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.history = Path(self.temp.name) / "BTC_5m.csv"
        with self.history.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
            writer.writeheader()
            for i in range(60):
                p = 100 + i * 0.1
                writer.writerow({"timestamp": 1700000100 + i * 300,
                                 "open": p - 0.01, "high": p + 0.1,
                                 "low": p - 0.1, "close": p, "volume": 20})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), v28.make_handler(self.history))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def get(self, path):
        with urlopen(self.base + path, timeout=3) as response:
            return response.status, json.load(response)

    def test_health_and_events(self):
        status, health = self.get("/health")
        self.assertEqual(status, 200)
        self.assertFalse(health["orders_enabled"])
        status, payload = self.get("/api/v1/agents")
        self.assertEqual(status, 200)
        self.assertFalse(payload["realtime"])
        self.assertFalse(payload["orders_enabled"])
        self.assertEqual(len(payload["events"]["events"]), 7)

    def test_read_only(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base + "/api/v1/agents", data=b"{}",
                            method="POST"), timeout=3)
        self.assertEqual(error.exception.code, 405)

    def test_missing_history_returns_503(self):
        self.history.unlink()
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/agents")
        self.assertEqual(error.exception.code, 503)

    def test_meeting_unavailable_fails_closed_without_orders(self):
        with patch("meeting_quality_report_v166.build_report",
                   side_effect=FileNotFoundError("missing snapshot")):
            with self.assertRaises(HTTPError) as error:
                self.get("/api/v1/meeting")
            self.assertEqual(error.exception.code, 503)
            payload = json.load(error.exception)
            self.assertEqual(payload["error"], "meeting_snapshot_unavailable")
            self.assertFalse(payload["orders_enabled"])
            self.assertFalse(payload["live_trading_approved"])
            self.assertFalse(payload["contract_validation"]["verified"])

    def test_meeting_snapshot_reports_contract_validation(self):
        with patch("meeting_quality_report_v166.build_report",
                   return_value={"status": "RESEARCH_ONLY"}) as report:
            with patch("meeting_contract_validator_v186.validate_meeting_snapshot",
                       return_value={"verified": False, "status": "BLOCKED"}) as validate:
                status, payload = self.get("/api/v1/meeting")
        self.assertEqual(status, 200)
        self.assertEqual(payload["contract_validation"]["status"], "BLOCKED")
        report.assert_called_once()
        validate.assert_called_once()

    def test_meeting_get_never_invokes_live_model_or_orders(self):
        # A dashboard refresh must only read a stored research snapshot.
        with patch("meeting_quality_report_v166.build_report",
                   return_value={"research_only": True, "orders_enabled": False,
                                 "live_trading_approved": False}):
            with patch("meeting_contract_validator_v186.validate_meeting_snapshot",
                       return_value={"verified": False, "status": "BLOCKED"}):
                with patch("ai_meeting_runtime.OpenAIProvider.complete",
                           side_effect=AssertionError("live model invoked")) as live:
                    status, payload = self.get("/api/v1/meeting")
        self.assertEqual(status, 200)
        self.assertFalse(payload["orders_enabled"])
        self.assertFalse(payload["live_trading_approved"])
        live.assert_not_called()

    def test_meeting_post_is_rejected_without_running_model(self):
        with patch("ai_meeting_runtime.OpenAIProvider.complete",
                   side_effect=AssertionError("live model invoked")) as live:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(self.base + "/api/v1/meeting", data=b"{}",
                                method="POST"), timeout=3)
        self.assertEqual(error.exception.code, 405)
        self.assertFalse(json.load(error.exception).get("orders_enabled", False))
        live.assert_not_called()

    def test_transcript_endpoint_missing_fails_closed(self):
        with patch.object(v28, "MEETING_TRANSCRIPT_PATH",
                          Path(self.temp.name) / "absent.json"):
            with self.assertRaises(HTTPError) as error:
                self.get("/api/v1/meeting/transcript")
        self.assertEqual(error.exception.code, 503)
        payload = json.load(error.exception)
        self.assertFalse(payload["orders_enabled"])

    def test_transcript_endpoint_rejects_untrusted_payload(self):
        target = Path(self.temp.name) / "meeting.json"
        target.write_text(json.dumps({"version": "AI_MEETING_1",
                                      "status": "COMPLETED", "orders_enabled": True}),
                          encoding="utf-8")
        with patch.object(v28, "MEETING_TRANSCRIPT_PATH", target):
            with self.assertRaises(HTTPError) as error:
                self.get("/api/v1/meeting/transcript")
        self.assertEqual(error.exception.code, 503)

    def test_transcript_endpoint_projects_only_safe_fields(self):
        target = Path(self.temp.name) / "meeting.json"
        entries = [{"agent": agent, "phase": phase, "summary": "Research only",
                    "concerns": [], "verdict": "INSUFFICIENT_DATA",
                    "secret_extra": "must not leak"}
                   for agent, phase in [
                       ("ATLAS", "ANALYSIS"), ("QUANT", "ANALYSIS"),
                       ("GUARDIAN", "ANALYSIS"), ("ATLAS", "PEER_REVIEW"),
                       ("QUANT", "PEER_REVIEW"), ("GUARDIAN", "PEER_REVIEW"),
                       ("COMMANDER", "CONCLUSION")]]
        payload = {"version": "AI_MEETING_1", "status": "COMPLETED",
                   "research_only": True, "orders_enabled": False,
                   "trade_authorization": "DENIED", "ai_agents_running": False,
                   "execution_mode": "OFFLINE_FIXTURE",
                   "model_inference_performed": False, "call_count": 7,
                   "transcript": entries, "secret_extra": "must not leak"}
        now = datetime.now(timezone.utc)
        payload.update({"market_source": "BYBIT_USDT_PERPETUAL_5M",
                        "model": "fixture", "request_sha256": "a" * 64,
                        "source_generated_at_utc": (now - timedelta(minutes=5)).isoformat(),
                        "started_at_utc": (now - timedelta(minutes=4)).isoformat(),
                        "generated_at_utc": (now - timedelta(minutes=3)).isoformat(),
                        "final_verdict": "INSUFFICIENT_DATA"})
        target.write_text(json.dumps(payload), encoding="utf-8")
        with patch.object(v28, "MEETING_TRANSCRIPT_PATH", target):
            status, result = self.get("/api/v1/meeting/transcript")
        self.assertEqual(status, 200)
        self.assertFalse(result["model_inference_performed"])
        self.assertFalse(result["orders_enabled"])
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["call_count"], 7)
        self.assertEqual(result["trade_authorization"], "DENIED")
        self.assertFalse(result["ai_agents_running"])
        self.assertEqual(len(result["transcript"]), 7)
        self.assertNotIn("secret_extra", result)
        self.assertNotIn("secret_extra", result["transcript"][0])

    def test_transcript_rejects_expired_source_even_if_completed(self):
        target = Path(self.temp.name) / "expired.json"
        now = datetime.now(timezone.utc)
        entries = [{"agent": a, "phase": p, "summary": "No trade",
                    "concerns": [], "verdict": "INSUFFICIENT_DATA"}
                   for a, p in [("ATLAS", "ANALYSIS"), ("QUANT", "ANALYSIS"),
                                ("GUARDIAN", "ANALYSIS"), ("ATLAS", "PEER_REVIEW"),
                                ("QUANT", "PEER_REVIEW"), ("GUARDIAN", "PEER_REVIEW"),
                                ("COMMANDER", "CONCLUSION")]]
        payload = {"version": "AI_MEETING_1", "status": "COMPLETED",
                   "research_only": True, "orders_enabled": False,
                   "trade_authorization": "DENIED", "ai_agents_running": False,
                   "execution_mode": "OFFLINE_FIXTURE",
                   "model_inference_performed": False, "call_count": 7,
                   "transcript": entries, "market_source": "BYBIT_USDT_PERPETUAL_5M",
                   "model": "fixture", "request_sha256": "a" * 64,
                   "source_generated_at_utc": (now - timedelta(hours=9)).isoformat(),
                   "started_at_utc": (now - timedelta(minutes=4)).isoformat(),
                   "generated_at_utc": (now - timedelta(minutes=3)).isoformat(),
                   "final_verdict": "INSUFFICIENT_DATA"}
        target.write_text(json.dumps(payload), encoding="utf-8")
        with patch.object(v28, "MEETING_TRANSCRIPT_PATH", target):
            with self.assertRaises(HTTPError) as error:
                self.get("/api/v1/meeting/transcript")
        self.assertEqual(error.exception.code, 503)
        self.assertFalse(json.load(error.exception)["orders_enabled"])

    def test_transcript_post_rejected(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base + "/api/v1/meeting/transcript",
                            data=b"{}", method="POST"), timeout=3)
        self.assertEqual(error.exception.code, 405)

    @unittest.skipUnless(shutil.which("node"), "Node.js required for room script test")
    def test_offline_meeting_report_reaches_actual_room_script(self):
        # Full offline boundary: stored report -> loopback HTTP -> actual room JS.
        from ai_meeting_runtime import publish_report, run_meeting
        from test_ai_meeting_runtime import Fixture
        from test_v240_provider_transport_preflight import request, NOW
        from copy import deepcopy
        bundle = deepcopy(request())
        # Runtime fixture does not use the network or any model provider.
        report = run_meeting(bundle, Fixture(), clock=lambda: NOW)
        now = datetime.now(timezone.utc)
        report["source_generated_at_utc"] = (now - timedelta(minutes=5)).isoformat()
        report["started_at_utc"] = (now - timedelta(minutes=4)).isoformat()
        report["generated_at_utc"] = (now - timedelta(minutes=3)).isoformat()
        report["market_source"] = "BYBIT_USDT_PERPETUAL_5M"
        target = Path(self.temp.name) / "meeting.json"
        publish_report(report, target)
        self.server.RequestHandlerClass = v28.make_handler(
            self.history, meeting_transcript_path=target)
        with patch.object(v28, "MEETING_TRANSCRIPT_PATH", target.with_name("missing-default.json")):
            status, payload = self.get("/api/v1/meeting/transcript")
        self.assertEqual(status, 200)
        self.assertFalse(payload["model_inference_performed"])
        self.assertFalse(payload["orders_enabled"])
        self.assertEqual(payload["status"], "COMPLETED")
        self.assertEqual(payload["call_count"], 7)
        self.assertEqual(payload["trade_authorization"], "DENIED")
        self.assertFalse(payload["ai_agents_running"])
        html = (Path(__file__).resolve().parent.parent / "web" /
                "office_3d.html").read_text(encoding="utf-8")
        script = '/* Completed'+html.split('/* Completed model meeting snapshots only.', 1)[1].split("</script>", 1)[0]
        harness = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const data=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const makeElement=()=>({
 children:[],disabled:false,hidden:false,style:{},attrs:{},events:{},dataset:{},
 focus(){this.focused=true},scrollIntoView(){this.scrolled=true},
 addEventListener(name,fn){this.events[name]=fn},
 setAttribute(name,value){this.attrs[name]=value},
 replaceChildren(...items){this.children=items},
 set innerHTML(_){throw Error('unsafe HTML')}
});
const elements={};
for(const id of ['ai-meeting-verdict-filter','ai-meeting-view-reset','ai-meeting-search','ai-meeting-phase-filter','ai-meeting-agent-controls','ai-meeting-agent-filter','ai-meeting-agent-count','ai-meeting-panel','ai-meeting-summary','ai-meeting-shortcut','ai-meeting-shortcut-status','meeting-progress-open-record','ai-meeting-selected-run','ai-meeting-clear-selection',
 'ai-meeting-status','ai-meeting-rows','ai-meeting-refresh',
 'ai-meeting-timeline','ai-meeting-linked','ai-meeting-decision','ai-meeting-connection-label'])
 elements[id]=makeElement();
let requested=null,failRequest=false,requestCount=0,holdResponse=null;
const documentEvents={},windowEvents={};
const panelEvents=[];
class ViewEvent{constructor(type,options){this.type=type;this.detail=options.detail}}
const window={addEventListener:(name,fn)=>{windowEvents[name]=fn}};
const document={dispatchEvent:event=>{panelEvents.push(event);return true},hidden:false,getElementById:id=>elements[id],addEventListener:(name,fn)=>{documentEvents[name]=fn},
 createElement:makeElement};
const callbacks=[],timeouts=new Map();
let timeoutId=0,timeoutPhase=null,bodyFault=null,httpStatus=null,networkFault=false;
let now=Date.now();
class Clock extends Date{static now(){return now}}
vm.runInNewContext(data.script,{document,window,Date:Clock,AbortController,CustomEvent:ViewEvent,
 setTimeout:(fn,ms)=>{assert.equal(ms,5000);const id=++timeoutId;timeouts.set(id,fn);return id},
 clearTimeout:id=>timeouts.delete(id),setInterval:fn=>callbacks.push(fn),
 fetch:async (url,options)=>{requested=url;requestCount++;
 if(networkFault)throw new TypeError("Failed to fetch internal-host.example:1234");
 if(httpStatus!==null)return {ok:false,status:httpStatus,text:async()=>{throw Error("error body must not be read")}};
 if(bodyFault){
  const fault=bodyFault;
  return {ok:true,text:async()=>{
   if(fault==='read-error')throw new TypeError('body stream interrupted');
   if(fault==='truncated')return '{"version":';
   if(fault==='oversized')return ' '.repeat(65537);
   return 'null';
  }};
 }
 if(timeoutPhase){
  assert.ok(options.signal instanceof AbortSignal);
  const pending=()=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>{
   const error=new Error('aborted');error.name='AbortError';reject(error);
  },{once:true}));
  if(timeoutPhase==='headers')return await pending();
  return {ok:true,text:pending};
 }
if(holdResponse)return await new Promise(resolve=>{holdResponse=resolve});return {ok:!failRequest,text:async()=>JSON.stringify(data.payload)}}});
setImmediate(async()=>{
 try{
  assert.equal(requested,'/api/v1/meeting/transcript');
  assert.equal(elements['ai-meeting-shortcut-status'].attrs['data-connection'],'validated');
  assert.match(elements['ai-meeting-shortcut-status'].textContent,/오프라인 테스트/);
  const agentView=elements['ai-meeting-agent-filter'],allRows=elements['ai-meeting-rows'];
  const fullDecision=elements['ai-meeting-decision'].textContent;
  const beforeFilter=requestCount;
  for(const [agent,expected] of [['ATLAS',2],['QUANT',2],['GUARDIAN',2],['COMMANDER',1],['ALL',7],['<script>',7]]){
   agentView.value=agent;agentView.events.change();
   assert.equal(allRows.children.filter(row=>!row.hidden).length,expected);
   assert.equal(elements['ai-meeting-decision'].textContent,fullDecision,'filter must not recompute final summary');
   assert.equal(requestCount,beforeFilter,'filter reads only already validated rows');
  }
  assert.equal(agentView.value,'ALL');assert.equal(elements['ai-meeting-agent-controls'].hidden,false);
  const phaseView=elements['ai-meeting-phase-filter'];
  for(const [agent,phase,expected] of [['ALL','ANALYSIS',3],['ALL','PEER_REVIEW',3],['ALL','CONCLUSION',1],['QUANT','PEER_REVIEW',1],['COMMANDER','ANALYSIS',0],['ALL','invalid',7]]){
   agentView.value=agent;phaseView.value=phase;phaseView.events.change();
   assert.equal(allRows.children.filter(row=>!row.hidden).length,expected);
   assert.equal(elements['ai-meeting-decision'].textContent,fullDecision);assert.equal(requestCount,beforeFilter);
   if(expected===0)assert.match(elements['ai-meeting-agent-count'].textContent,/표시할 발언 없음/);
  }
  assert.equal(phaseView.value,'ALL');
  const searchView=elements['ai-meeting-search'];
  searchView.value=data.payload.transcript[0].summary.slice(0,30).toUpperCase();searchView.events.input();
  assert.equal(allRows.children[0].hidden,false,'search is case-insensitive and matches summary text');
  if(data.payload.transcript[0].concerns.length){searchView.value=data.payload.transcript[0].concerns[0].slice(0,30);searchView.events.input();assert.equal(allRows.children[0].hidden,false,'concerns are searchable');}
  searchView.value='a^$[literal]';searchView.events.input();assert.equal(allRows.children.filter(row=>!row.hidden).length,0);
  assert.match(elements['ai-meeting-agent-count'].textContent,/표시할 발언 없음/);
  searchView.value='   ';searchView.events.input();assert.equal(allRows.children.filter(row=>!row.hidden).length,7);
  assert.equal(elements['ai-meeting-decision'].textContent,fullDecision);assert.equal(requestCount,beforeFilter);

  const viewReset=elements['ai-meeting-view-reset'];
  assert.equal(viewReset.disabled,false,'whitespace can be cleared even though it matches all rows');
  viewReset.events.click();assert.equal(searchView.value,'');assert.equal(viewReset.disabled,true);assert.equal(searchView.focused,true);
  const beforeEmptyReset=requestCount;viewReset.events.click();assert.equal(requestCount,beforeEmptyReset);
  agentView.value='COMMANDER';phaseView.value='ANALYSIS';searchView.value='literal-no-match';searchView.events.input();
  assert.equal(allRows.children.filter(row=>!row.hidden).length,0);viewReset.events.click();
  assert.equal(agentView.value,'ALL');assert.equal(phaseView.value,'ALL');assert.equal(searchView.value,'');
  assert.equal(allRows.children.filter(row=>!row.hidden).length,7);assert.equal(requestCount,beforeFilter);
  assert.equal(elements['ai-meeting-decision'].textContent,fullDecision);

  // Polling preserves a view only after an identical record validates again.
  agentView.value='QUANT';phaseView.value='PEER_REVIEW';searchView.value='a^$[literal]';searchView.events.input();
  const beforePreservedPoll=requestCount;callbacks[1]();await new Promise(setImmediate);
  assert.equal(requestCount,beforePreservedPoll+1);assert.equal(agentView.value,'QUANT');assert.equal(phaseView.value,'PEER_REVIEW');assert.equal(searchView.value,'a^$[literal]');
  assert.equal(allRows.children.filter(row=>!row.hidden).length,0);assert.equal(elements['ai-meeting-decision'].textContent,fullDecision);
  document.hidden=true;const beforeHiddenView=requestCount;
  documentEvents.visibilitychange();windowEvents.pageshow({persisted:true});windowEvents.online();
  assert.equal(requestCount,beforeHiddenView);
  document.hidden=false;documentEvents.visibilitychange();await new Promise(setImmediate);
  assert.equal(agentView.value,'QUANT');assert.equal(phaseView.value,'PEER_REVIEW');assert.equal(searchView.value,'a^$[literal]');
  windowEvents.pageshow({persisted:true});await new Promise(setImmediate);
  assert.equal(agentView.value,'QUANT');assert.equal(searchView.value,'a^$[literal]');
  windowEvents.online();await new Promise(setImmediate);assert.equal(searchView.value,'a^$[literal]');
  const originalModel=data.payload.model;data.payload.model='changed-record-model';windowEvents.pageshow({persisted:true});await new Promise(setImmediate);
  assert.equal(agentView.value,'ALL');assert.equal(phaseView.value,'ALL');assert.equal(searchView.value,'');
  data.payload.model=originalModel;await elements['ai-meeting-refresh'].events.click();
  searchView.value='retained-until-failure';searchView.events.input();failRequest=true;callbacks[1]();await new Promise(setImmediate);
  assert.equal(searchView.value,'');assert.equal(elements['ai-meeting-agent-controls'].hidden,true);
  failRequest=false;callbacks[1]();await new Promise(setImmediate);assert.equal(searchView.value,'');assert.equal(agentView.value,'ALL');
  searchView.value='manual-reset';searchView.events.input();await elements['ai-meeting-refresh'].events.click();assert.equal(searchView.value,'');
  // Scheduled reads cannot hide focused search/select controls while editing.
  for(const control of [agentView,phaseView,elements['ai-meeting-verdict-filter'],searchView]){
   document.activeElement=control;const beforeEditingPoll=requestCount;callbacks[1]();
   assert.equal(requestCount,beforeEditingPoll);assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated');
  }
  const beforeEditingManual=requestCount;await elements['ai-meeting-refresh'].events.click();
  assert.equal(requestCount,beforeEditingManual+1,'manual refresh still works while a control has focus');
  const beforeExpiry=now;now+=9*3600000;callbacks[0]();
  assert.equal(elements['ai-meeting-rows'].children.length,0,'focus must not suppress expiration');
  assert.equal(elements['ai-meeting-agent-controls'].hidden,true);
  now=beforeExpiry;document.activeElement=null;await elements['ai-meeting-refresh'].events.click();
  const beforeUnfocusedPoll=requestCount;callbacks[1]();await new Promise(setImmediate);assert.equal(requestCount,beforeUnfocusedPoll+1);
  const verdictView=elements['ai-meeting-verdict-filter'],cleanRecord=JSON.parse(JSON.stringify(data.payload));
  data.payload.transcript[2].verdict='REVIEW_NEEDED';data.payload.final_verdict='REVIEW_NEEDED';
  await elements['ai-meeting-refresh'].events.click();assert.equal(allRows.children.length,7);
  const riskSummary=elements['ai-meeting-decision'].textContent,riskReads=requestCount;
  verdictView.value='REVIEW_NEEDED';verdictView.events.change();
  assert.equal(allRows.children.filter(row=>!row.hidden).length,1);assert.equal(allRows.children[2].hidden,false);
  phaseView.value='PEER_REVIEW';phaseView.events.change();assert.equal(allRows.children.filter(row=>!row.hidden).length,0);
  assert.equal(elements['ai-meeting-decision'].textContent,riskSummary);assert.equal(requestCount,riskReads);
  viewReset.events.click();assert.equal(verdictView.value,'ALL');assert.equal(allRows.children.filter(row=>!row.hidden).length,7);
  data.payload.transcript[0].verdict='INSUFFICIENT_DATA';data.payload.final_verdict='INSUFFICIENT_DATA';
  await elements['ai-meeting-refresh'].events.click();verdictView.value='INSUFFICIENT_DATA';verdictView.events.change();
  assert.equal(allRows.children.filter(row=>!row.hidden).length,1);assert.equal(allRows.children[0].hidden,false);
  callbacks[1]();await new Promise(setImmediate);assert.equal(verdictView.value,'INSUFFICIENT_DATA');
  verdictView.value='INVALID';verdictView.events.change();assert.equal(verdictView.value,'ALL');
  data.payload=cleanRecord;await elements['ai-meeting-refresh'].events.click();
  const beforeShortcut=requestCount;
  elements['ai-meeting-shortcut'].events.click();
  assert.equal(elements['ai-meeting-panel'].open,true);
  assert.equal(elements['ai-meeting-summary'].focused,true);
  assert.equal(elements['ai-meeting-panel'].scrolled,true);
  assert.equal(requestCount,beforeShortcut,'navigation must not fetch or start a meeting');
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.match(elements['ai-meeting-status'].textContent,/실제 AI 실행 아님/);
  assert.ok(elements['ai-meeting-rows'].children.every(x=>typeof x.textContent==='string'));
  const timeline=elements['ai-meeting-timeline'];
  assert.equal(timeline.hidden,false);
  assert.equal(timeline.children.length,5);
  const atlas=timeline.children[1],quant=timeline.children[2],commander=timeline.children[4];
  assert.equal(atlas.attrs.role,'button');
  assert.equal(atlas.attrs['aria-pressed'],'false');
  atlas.events.click();
  assert.equal(atlas.attrs['aria-pressed'],'true');
  assert.equal(quant.attrs['aria-pressed'],'false');
  assert.equal(elements['ai-meeting-linked'].hidden,false);
  assert.match(elements['ai-meeting-linked'].textContent,/판단 비교/);
  assert.ok(elements['ai-meeting-linked'].textContent.includes('\n'),'analysis details must use real line breaks');
  assert.ok(!elements['ai-meeting-linked'].textContent.includes('\\n'),'analysis details must not show escaped newlines');
  assert.match(elements['ai-meeting-linked'].textContent,/재언급이 없다고 해결된 것은 아닙니다/);
  let prevented=false;
  quant.events.keydown({key:'Enter',preventDefault(){prevented=true}});
  assert.equal(prevented,true);
  assert.equal(quant.attrs['aria-pressed'],'true');
  assert.equal(atlas.attrs['aria-pressed'],'false');
  commander.events.click();
  assert.equal(commander.attrs['aria-pressed'],'true');
  assert.match(elements['ai-meeting-linked'].textContent,/COMMANDER 최종 결론/);
  assert.ok(elements['ai-meeting-linked'].textContent.includes('\n'),'conclusion must use real line breaks');
  assert.ok(!elements['ai-meeting-linked'].textContent.includes('\\n'),'conclusion must not show escaped newlines');
  assert.ok(callbacks.length>=2,'expiry and polling callbacks must exist');
  now=Date.parse(data.payload.source_generated_at_utc)+8*3600000+1000;
  callbacks[0]();
  assert.equal(elements['ai-meeting-rows'].children.length,0);
  assert.equal(timeline.children.length,0);
  assert.equal(timeline.hidden,true);
  assert.equal(elements['ai-meeting-linked'].hidden,true);
  assert.equal(elements['ai-meeting-decision'].hidden,true);
  assert.match(elements['ai-meeting-status'].textContent,/만료/);
  // Restore the clock to a valid instant, then exercise the actual refresh button.
  now=Date.now();
  assert.equal(typeof elements['ai-meeting-refresh'].events.click,'function');
  await elements['ai-meeting-refresh'].events.click();
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.equal(timeline.children.length,5);
  assert.equal(timeline.hidden,false);
  assert.equal(elements['ai-meeting-linked'].hidden,true);
  assert.equal(elements['ai-meeting-decision'].hidden,false);
  assert.match(elements['ai-meeting-status'].textContent,/오프라인 테스트 기록/);
  // A subsequent HTTP error must fail closed, not preserve a stale decision.
  failRequest=true;
  await elements['ai-meeting-refresh'].events.click();
  assert.equal(elements['ai-meeting-rows'].children.length,0);
  assert.equal(timeline.children.length,0);
  assert.equal(timeline.hidden,true);
  assert.equal(elements['ai-meeting-linked'].hidden,true);
  assert.equal(elements['ai-meeting-decision'].hidden,true);
  assert.equal(elements['ai-meeting-refresh'].disabled,false);
  assert.equal(elements['ai-meeting-rows'].attrs['aria-busy'],'false');
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected');
  // A later successful retry must recover without reusing stale selections.
  failRequest=false;
  await elements['ai-meeting-refresh'].events.click();
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.equal(timeline.children.length,5);
  assert.equal(timeline.hidden,false);
  assert.equal(elements['ai-meeting-linked'].hidden,true);
  assert.equal(elements['ai-meeting-decision'].hidden,false);
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated');
  assert.equal(elements['ai-meeting-refresh'].disabled,false);
  assert.equal(elements['ai-meeting-rows'].attrs['aria-busy'],'false');
  // A malformed but HTTP-successful response must also fail closed.
  data.payload.call_count=6;
  await elements['ai-meeting-refresh'].events.click();
  assert.equal(elements['ai-meeting-rows'].children.length,0);
  assert.equal(timeline.children.length,0);
  assert.equal(timeline.hidden,true);
  assert.equal(elements['ai-meeting-linked'].hidden,true);
  assert.equal(elements['ai-meeting-decision'].hidden,true);
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected');
  assert.equal(elements['ai-meeting-refresh'].disabled,false);
  assert.equal(elements['ai-meeting-rows'].attrs['aria-busy'],'false');
  data.payload.call_count=7;
  await elements['ai-meeting-refresh'].events.click();
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated');
  // Security-sensitive flags must never be accepted from a transcript response.
  for(const [field,invalid] of [['orders_enabled',true],['trade_authorization','ALLOWED'],['research_only',false]]){
   const original=data.payload[field];
   data.payload[field]=invalid;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,0,field);
   assert.equal(timeline.children.length,0,field);
   assert.equal(elements['ai-meeting-decision'].hidden,true,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected',field);
   data.payload[field]=original;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,7,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated',field);
  }
  // Offline fixtures must never masquerade as actual model inference.
  for(const [field,invalid] of [['model_inference_performed',true],['ai_agents_running',true],['execution_mode','LIVE_PROVIDER']]){
   const original=data.payload[field];
   data.payload[field]=invalid;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,0,field);
   assert.equal(timeline.children.length,0,field);
   assert.equal(elements['ai-meeting-decision'].hidden,true,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected',field);
   data.payload[field]=original;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,7,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated',field);
  }
  // Corrupted transcript order and peer-review references must fail closed.
  for(const field of ['transcript','statement_refs']){
   const original=data.payload[field];
   assert.ok(Array.isArray(original)&&original.length===7,field);
   const tampered=original.map(item=>({...item}));
   if(field==='transcript'){
    [tampered[0],tampered[1]]=[tampered[1],tampered[0]];
   }else{
    tampered[3]={...tampered[3],references:['M02']};
   }
   data.payload[field]=tampered;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,0,field);
   assert.equal(timeline.children.length,0,field);
   assert.equal(elements['ai-meeting-decision'].hidden,true,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected',field);
   data.payload[field]=original;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,7,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated',field);
  }
  // Future and expired source timestamps must never be shown as current.
  const originalSource=data.payload.source_generated_at_utc;
  for(const invalidSource of [
   new Date(Date.now()+60*60*1000).toISOString(),
   new Date(Date.now()-9*60*60*1000).toISOString()
  ]){
   data.payload.source_generated_at_utc=invalidSource;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,0,'invalid source timestamp');
   assert.equal(timeline.children.length,0,'invalid source timestamp');
   assert.equal(elements['ai-meeting-decision'].hidden,true,'invalid source timestamp');
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected');
   data.payload.source_generated_at_utc=originalSource;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,7);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated');
  }
  // Chronologically impossible meeting timestamps must fail closed.
  for(const [field,invalid] of [
   ['started_at_utc',new Date(Date.parse(data.payload.source_generated_at_utc)-1000).toISOString()],
   ['generated_at_utc',new Date(Date.parse(data.payload.started_at_utc)-1000).toISOString()],
   ['generated_at_utc',new Date(Date.now()+60*60*1000).toISOString()]
  ]){
   const original=data.payload[field];
   data.payload[field]=invalid;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,0,field);
   assert.equal(timeline.children.length,0,field);
   assert.equal(elements['ai-meeting-decision'].hidden,true,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected',field);
   data.payload[field]=original;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,7,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated',field);
  }
  // Reject malformed model identity and request digest metadata.
  for(const [field,invalid] of [
   ['model',''],
   ['model','x'.repeat(121)],
   ['request_sha256',''],
   ['request_sha256','g'.repeat(64)],
   ['request_sha256','a'.repeat(63)]
  ]){
   const original=data.payload[field];
   data.payload[field]=invalid;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,0,field);
   assert.equal(timeline.children.length,0,field);
   assert.equal(elements['ai-meeting-decision'].hidden,true,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected',field);
   data.payload[field]=original;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,7,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated',field);
  }
  // Transcript statement content must satisfy strict bounds and types.
  for(const [field,invalid] of [
   ['summary',''],
   ['summary','x'.repeat(1601)],
   ['concerns',['']],
   ['concerns',['x'.repeat(401)]],
   ['concerns',Array(9).fill('concern')],
   ['concerns','not-an-array']
  ]){
   const original=data.payload.transcript[0][field];
   data.payload.transcript[0][field]=invalid;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,0,field);
   assert.equal(timeline.children.length,0,field);
   assert.equal(elements['ai-meeting-decision'].hidden,true,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected',field);
   data.payload.transcript[0][field]=original;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,7,field);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated',field);
  }
  // Invalid verdicts or contradictory final verdicts must never be shown.
  for(const [target,invalid] of [
   ['statement','UNRECOGNIZED_VERDICT'],
   ['final','UNRECOGNIZED_VERDICT']
  ]){
   const isFinal=target==='final';
   const original=isFinal?data.payload.final_verdict:data.payload.transcript[0].verdict;
   if(isFinal)data.payload.final_verdict=invalid;
   else data.payload.transcript[0].verdict=invalid;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,0,target);
   assert.equal(timeline.children.length,0,target);
   assert.equal(elements['ai-meeting-decision'].hidden,true,target);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected',target);
   if(isFinal)data.payload.final_verdict=original;
   else data.payload.transcript[0].verdict=original;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,7,target);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated',target);
  }
  // Rapid refresh and background polling must not create concurrent fetches.
  holdResponse=true;
  const beforeOverlap=requestCount;
  const firstRefresh=elements['ai-meeting-refresh'].events.click();
  assert.equal(requestCount,beforeOverlap+1);
  assert.equal(elements['ai-meeting-refresh'].disabled,true);
  assert.equal(elements['ai-meeting-rows'].attrs['aria-busy'],'true');
  assert.equal(elements['ai-meeting-shortcut-status'].attrs['data-connection'],'loading');
  await elements['ai-meeting-refresh'].events.click();
  await callbacks[1]();
  assert.equal(requestCount,beforeOverlap+1,'overlapping refresh must not fetch twice');
  assert.equal(elements['ai-meeting-rows'].children.length,0,'stale meeting cleared while loading');
  const release=holdResponse;
  holdResponse=null;
  release({ok:true,text:async()=>JSON.stringify(data.payload)});
  await firstRefresh;
  assert.equal(elements['ai-meeting-refresh'].disabled,false);
  assert.equal(elements['ai-meeting-rows'].attrs['aria-busy'],'false');
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated');
  assert.equal(timeouts.size,0,'successful requests release deadline timers');
  // Both stalled headers and a stalled response body must abort and allow retry.
  for(const phase of ['headers','body']){
   timeline.children[1].events.click();
   timeoutPhase=phase;
   const stalled=elements['ai-meeting-refresh'].events.click();
   await Promise.resolve();
   assert.equal(timeouts.size,1,phase);
   assert.equal(elements['ai-meeting-refresh'].disabled,true,phase);
   for(const fire of [...timeouts.values()])fire();
   await stalled;
   assert.equal(timeouts.size,0,phase);
   assert.equal(elements['ai-meeting-rows'].children.length,0,phase);
   assert.equal(timeline.children.length,0,phase);
   assert.equal(elements['ai-meeting-linked'].hidden,true,phase);
   assert.equal(elements['ai-meeting-decision'].hidden,true,phase);
   assert.match(elements['ai-meeting-status'].textContent,/응답 시간 초과/,phase);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected',phase);
   assert.equal(elements['ai-meeting-refresh'].disabled,false,phase);
   assert.equal(elements['ai-meeting-rows'].attrs['aria-busy'],'false',phase);
   timeoutPhase=null;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,7,phase);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated',phase);
   assert.equal(timeouts.size,0,phase);
  }
  // Returning from a hidden mobile tab must retry even after expiry or failure.
  const flush=()=>new Promise(resolve=>setImmediate(resolve));
  document.hidden=true;
  const beforeHidden=requestCount;
  callbacks[1]();
  documentEvents.visibilitychange();
  await flush();
  assert.equal(requestCount,beforeHidden,'hidden tabs must not poll');
  now=Date.parse(data.payload.source_generated_at_utc)+8*3600000+1000;
  document.hidden=false;
  documentEvents.visibilitychange();
  await flush();
  assert.equal(requestCount,beforeHidden+1,'returning after expiry must refresh');
  assert.equal(elements['ai-meeting-rows'].children.length,0);
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected');
  now=Date.now();
  failRequest=true;
  document.hidden=true;documentEvents.visibilitychange();
  document.hidden=false;documentEvents.visibilitychange();
  await flush();
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected');
  failRequest=false;
  holdResponse=true;
  document.hidden=true;documentEvents.visibilitychange();
  const beforeReturn=requestCount;
  document.hidden=false;documentEvents.visibilitychange();
  documentEvents.visibilitychange();callbacks[1]();
  assert.equal(requestCount,beforeReturn+1,'visibility and polling must share request guard');
  const resume=holdResponse;holdResponse=null;
  resume({ok:true,text:async()=>JSON.stringify(data.payload)});
  await flush();
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated');
  assert.equal(elements['ai-meeting-refresh'].disabled,false);
  assert.equal(timeouts.size,0);
  // BFCache restoration uses pageshow, which need not emit visibilitychange.
  assert.equal(typeof windowEvents.pageshow,'function');
  const beforeRestore=requestCount;
  windowEvents.pageshow({persisted:false});
  document.hidden=true;windowEvents.pageshow({persisted:true});
  await flush();
  assert.equal(requestCount,beforeRestore,'initial or hidden pageshow must not fetch');
  document.hidden=false;
  now=Date.parse(data.payload.source_generated_at_utc)+9*3600000;
  holdResponse=true;
  windowEvents.pageshow({persisted:true});
  documentEvents.visibilitychange();callbacks[1]();
  assert.equal(requestCount,beforeRestore+1,'restoration shares the request guard');
  assert.equal(elements['ai-meeting-rows'].children.length,0);
  assert.equal(elements['ai-meeting-decision'].hidden,true);
  const restore=holdResponse;holdResponse=null;
  restore({ok:true,text:async()=>JSON.stringify(data.payload)});
  await flush();
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected');
  now=Date.now();
  windowEvents.pageshow({persisted:true});
  await flush();
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated');
  assert.equal(elements['ai-meeting-refresh'].disabled,false);
  assert.equal(timeouts.size,0);
  // HTTP 200 does not guarantee a complete, bounded, valid JSON body.
  for(const fault of ['read-error','truncated','oversized','null']){
   timeline.children[1].events.click();
   bodyFault=fault;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,0,fault);
   assert.equal(timeline.children.length,0,fault);
   assert.equal(elements['ai-meeting-linked'].hidden,true,fault);
   assert.equal(elements['ai-meeting-decision'].hidden,true,fault);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected',fault);
   assert.equal(elements['ai-meeting-refresh'].disabled,false,fault);
   assert.equal(elements['ai-meeting-rows'].attrs['aria-busy'],'false',fault);
   assert.equal(timeouts.size,0,fault);
   if(fault==='oversized')assert.match(elements['ai-meeting-status'].textContent,/크기 초과/);
   if(fault==='read-error')assert.match(elements['ai-meeting-status'].textContent,/수신이 중단/);
   if(fault==='truncated')assert.match(elements['ai-meeting-status'].textContent,/JSON 형식 오류/);
   if(fault==='null')assert.match(elements['ai-meeting-status'].textContent,/객체 형식 오류/);
   bodyFault=null;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,7,fault);
   assert.equal(elements['ai-meeting-linked'].hidden,true,fault);
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated',fault);
  }
  // Distinguish transport failures without reading or exposing server error bodies.
  for(const [code,message] of [[409,/선택한 실행과 다른/],[404,/API 경로/],[401,/접근이 거부/],[403,/접근이 거부/],
   [429,/요청이 많습니다/],[502,/응답 지연/],[504,/응답 지연/],
   [503,/완료된 모델 회의 결과/]]){
   httpStatus=code;
   await elements['ai-meeting-refresh'].events.click();
   assert.match(elements['ai-meeting-status'].textContent,message,String(code));
   assert.equal(elements['ai-meeting-rows'].children.length,0,String(code));
   assert.equal(elements['ai-meeting-shortcut-status'].attrs['data-connection'],'disconnected');
   assert.match(elements['ai-meeting-shortcut-status'].textContent,/요청 실패/);
   assert.equal(elements['ai-meeting-decision'].hidden,true,String(code));
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected');
   assert.equal(elements['ai-meeting-refresh'].disabled,false);
   assert.equal(timeouts.size,0);
   httpStatus=null;
   await elements['ai-meeting-refresh'].events.click();
   assert.equal(elements['ai-meeting-rows'].children.length,7,String(code));
   assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated');
  }
  // Optional transcript identity must be bounded and displayed as plain text.
  data.payload.workflow_execution_id='a'.repeat(32);
  await elements['ai-meeting-refresh'].events.click();
  assert.match(elements['ai-meeting-status'].textContent,/실행 ID: a{32}/);
  data.payload.workflow_execution_id='INVALID';
  await elements['ai-meeting-refresh'].events.click();
  assert.equal(elements['ai-meeting-rows'].children.length,0);
  assert.match(elements['ai-meeting-status'].textContent,/실행 ID 검증 실패/);
  delete data.payload.workflow_execution_id;
  await elements['ai-meeting-refresh'].events.click();
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  // Connectivity recovery refreshes visible tabs and shares all request guards.
  assert.equal(typeof windowEvents.online,'function');
  document.hidden=true;
  const beforeOnline=requestCount;
  windowEvents.online();
  await flush();
  assert.equal(requestCount,beforeOnline,'hidden online event must not fetch');
  document.hidden=false;
  failRequest=true;
  await elements['ai-meeting-refresh'].events.click();
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'disconnected');
  failRequest=false;holdResponse=true;
  const beforeReconnect=requestCount;
  windowEvents.online();windowEvents.online();
  documentEvents.visibilitychange();callbacks[1]();
  assert.equal(requestCount,beforeReconnect+1,'reconnection must not duplicate requests');
  assert.equal(elements['ai-meeting-rows'].children.length,0);
  assert.equal(elements['ai-meeting-refresh'].disabled,true);
  const reconnect=holdResponse;holdResponse=null;
  reconnect({ok:true,text:async()=>JSON.stringify(data.payload)});
  await flush();
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated');
  assert.equal(elements['ai-meeting-refresh'].disabled,false);
  assert.equal(timeouts.size,0);
  networkFault=true;
  await elements['ai-meeting-refresh'].events.click();
  assert.match(elements['ai-meeting-status'].textContent,/네트워크 연결을 확인/);
  assert.doesNotMatch(elements['ai-meeting-status'].textContent,/internal-host|Failed to fetch/);
  assert.equal(elements['ai-meeting-rows'].children.length,0);
  assert.equal(elements['ai-meeting-decision'].hidden,true);
  assert.equal(elements['ai-meeting-refresh'].disabled,false);
  assert.equal(timeouts.size,0);
  networkFault=false;
  await elements['ai-meeting-refresh'].events.click();
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated');
  // Explicit completed-run navigation cannot reuse a different or legacy transcript.
  const openRecord=elements['meeting-progress-open-record'];
  openRecord.disabled=true;openRecord.dataset.executionId='a'.repeat(32);
  const beforeDisabled=requestCount;
  await openRecord.events.click();assert.equal(requestCount,beforeDisabled);
  openRecord.disabled=false;
  await openRecord.events.click();
  assert.equal(elements['ai-meeting-rows'].children.length,0,'legacy transcript has no selected execution identity');
  assert.match(elements['ai-meeting-status'].textContent,/선택한 실행과 다른/);
  assert.equal(elements['ai-meeting-selected-run'].hidden,false);
  assert.match(elements['ai-meeting-selected-run'].textContent,/a{32}/);
  assert.equal(elements['ai-meeting-clear-selection'].hidden,false);
  data.payload.workflow_execution_id='a'.repeat(32);
  await openRecord.events.click();
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.equal(elements['ai-meeting-panel'].open,true);
  assert.equal(elements['ai-meeting-summary'].focused,true);
  data.payload.workflow_execution_id='b'.repeat(32);
  await elements['ai-meeting-refresh'].events.click();
  assert.equal(elements['ai-meeting-rows'].children.length,0);
  // A new selection while loading queues one reload and rejects the old response.
  data.payload.workflow_execution_id='a'.repeat(32);holdResponse=true;
  const beforeSelection=requestCount;
  const loadingOld=elements['ai-meeting-refresh'].events.click();
  openRecord.dataset.executionId='b'.repeat(32);
  await openRecord.events.click();
  await openRecord.events.click();
  data.payload.workflow_execution_id='b'.repeat(32);
  const releaseOld=holdResponse;holdResponse=null;
  releaseOld({ok:true,text:async()=>JSON.stringify({...data.payload,workflow_execution_id:'a'.repeat(32)})});
  await loadingOld;await flush();
  assert.equal(requestCount,beforeSelection+2,'selection changes queue only one additional fetch');
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.match(elements['ai-meeting-status'].textContent,/실행 ID: b{32}/);
  assert.match(elements['ai-meeting-selected-run'].textContent,/b{32}/);
  const beforePinnedReset=requestCount;searchView.value='no-match';searchView.events.input();viewReset.events.click();
  assert.match(elements['ai-meeting-selected-run'].textContent,/b{32}/);assert.equal(requestCount,beforePinnedReset);

  // Reset is an explicit read-only return to the server's default record.
  data.payload.workflow_execution_id='c'.repeat(32);
  await elements['ai-meeting-clear-selection'].events.click();
  assert.equal(elements['ai-meeting-selected-run'].hidden,true);
  assert.equal(elements['ai-meeting-selected-run'].textContent,'');
  assert.equal(elements['ai-meeting-clear-selection'].hidden,true);
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.match(elements['ai-meeting-status'].textContent,/실행 ID: c{32}/);
  const afterClear=requestCount;
  await elements['ai-meeting-clear-selection'].events.click();
  assert.equal(requestCount,afterClear,'clearing an absent selection must not fetch');
  assert.equal(timeouts.size,0);
  // Network loss clears the entire transcript and pauses its read paths.
  searchView.value='test';searchView.events.input();
  agentView.value='GUARDIAN';agentView.events.change();phaseView.value='PEER_REVIEW';phaseView.events.change();
  const beforeOffline=requestCount;windowEvents.offline();
  assert.equal(elements['ai-meeting-agent-controls'].hidden,true);assert.equal(viewReset.disabled,true);assert.equal(agentView.disabled,true);assert.equal(agentView.value,'ALL');assert.equal(elements['ai-meeting-agent-count'].textContent,'');assert.equal(phaseView.value,'ALL');assert.equal(phaseView.disabled,true);assert.equal(searchView.value,'');assert.equal(searchView.disabled,true);assert.equal(verdictView.value,'ALL');assert.equal(verdictView.disabled,true);
  assert.equal(elements['ai-meeting-rows'].children.length,0);assert.equal(elements['ai-meeting-decision'].hidden,true);
  assert.equal(elements['ai-meeting-timeline'].hidden,true);assert.equal(elements['ai-meeting-refresh'].disabled,true);
  assert.match(elements['ai-meeting-status'].textContent,/브라우저 네트워크 연결 없음/);
  callbacks[1]();await elements['ai-meeting-refresh'].events.click();assert.equal(requestCount,beforeOffline);
  document.hidden=true;windowEvents.online();await flush();assert.equal(requestCount,beforeOffline);
  document.hidden=false;documentEvents.visibilitychange();await flush();assert.equal(elements['ai-meeting-rows'].children.length,7);
  holdResponse=true;const oldRead=elements['ai-meeting-refresh'].events.click();windowEvents.offline();windowEvents.online();
  const priorNetwork=holdResponse;holdResponse=null;priorNetwork({ok:true,text:async()=>{throw Error('obsolete body must not be read')}});
  await oldRead;await flush();assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.equal(elements['ai-meeting-status'].attrs['data-connection'],'validated');assert.equal(elements['ai-meeting-refresh'].disabled,false);
  assert.equal(timeouts.size,0);
  // Disconnection cancels both waiting headers and a pending body read immediately.
  for(const phase of ['headers','body']){
   timeoutPhase=phase;const interrupted=elements['ai-meeting-refresh'].events.click();await flush();
   windowEvents.offline();await interrupted;
   assert.equal(timeouts.size,0,'canceled request releases its timeout');
   assert.match(elements['ai-meeting-status'].textContent,/브라우저 네트워크 연결 없음/);
   assert.doesNotMatch(elements['ai-meeting-status'].textContent,/시간 초과/);
   assert.equal(elements['ai-meeting-rows'].children.length,0);assert.equal(elements['ai-meeting-refresh'].disabled,true);
   timeoutPhase=null;windowEvents.online();await flush();assert.equal(elements['ai-meeting-rows'].children.length,7);
  }
  const rendered=panelEvents.filter(event=>event.type==='spacebar:transcript-view');
  assert.ok(rendered.length>0);
  assert.equal(rendered.at(-1).detail.state,'validated');
  assert.equal(rendered.at(-1).detail.execution_id,'c'.repeat(32));
  assert.equal(rendered.at(-1).detail.provenance,'OFFLINE_FIXTURE');
  assert.ok(rendered.every(event=>Object.keys(event.detail).sort().join(',')==='execution_id,provenance,state'));
  assert.ok(rendered.filter(event=>event.detail.state!=='validated').every(event=>event.detail.execution_id===null&&event.detail.provenance===null));
  process.exit(0);
 }catch(e){console.error(e);process.exit(1)}
});
"""
        result = subprocess.run([shutil.which("node"), "-e", harness],
                                input=json.dumps({"script": script, "payload": payload}),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_office3d_served_over_http_with_mobile_and_meeting_contract(self):
        # Verify the real dashboard server delivers the 3D room rather than a
        # local file:// page, with a responsive viewport and same-origin API.
        with urlopen(self.base + "/office3d", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.headers.get("Content-Type", ""))
            html = response.read().decode("utf-8")
        self.assertIn('name="viewport"', html)
        self.assertIn("width=device-width", html)
        self.assertIn("@media", html)
        self.assertIn('id="ai-meeting-panel"', html)
        self.assertIn('id="ai-meeting-rows"', html)
        self.assertIn('fetch("/api/v1/meeting/transcript"', html)
        self.assertIn("WebGLRenderer", html)
        self.assertIn("touch-action", html)
        self.assertNotIn("OPENAI_API_KEY", html)

    def test_office3d_query_string_keeps_same_origin_route(self):
        with urlopen(self.base + "/office3d?view=mobile", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"ai-meeting-panel", response.read())

    def test_configured_transcript_path_isolated_from_default(self):
        from ai_meeting_runtime import publish_report, run_meeting
        from test_ai_meeting_runtime import Fixture
        from test_v240_provider_transport_preflight import request, NOW
        report = run_meeting(request(), Fixture(), clock=lambda: NOW)
        now = datetime.now(timezone.utc)
        for field, minutes in [('source_generated_at_utc', 5),
                               ('started_at_utc', 4), ('generated_at_utc', 3)]:
            report[field] = (now - timedelta(minutes=minutes)).isoformat()
        report['market_source'] = 'BYBIT_USDT_PERPETUAL_5M'
        target = Path(self.temp.name) / 'runtime-output.json'
        publish_report(report, target)
        self.server.RequestHandlerClass = v28.make_handler(
            self.history, meeting_transcript_path=str(target))
        with patch.object(v28, 'MEETING_TRANSCRIPT_PATH', Path(self.temp.name) / 'missing.json'):
            status, payload = self.get('/api/v1/meeting/transcript')
        self.assertEqual(status, 200)
        self.assertEqual(len(payload['transcript']), 7)
        self.assertFalse(payload['orders_enabled'])
        self.assertFalse(payload['model_inference_performed'])
        # The real runtime publishes by atomic replacement; the handler must reread it.
        report['transcript'][0]['summary'] = 'Updated completed meeting observation'
        publish_report(report, target)
        status, updated = self.get('/api/v1/meeting/transcript')
        self.assertEqual(status, 200)
        self.assertEqual(updated['transcript'][0]['summary'], report['transcript'][0]['summary'])
        self.assertFalse(updated['orders_enabled'])
        # A stale replacement must be rejected, not served from a prior valid read.
        original_source = report['source_generated_at_utc']
        report['source_generated_at_utc'] = (now - timedelta(hours=9)).isoformat()
        publish_report(report, target)
        with self.assertRaises(HTTPError) as error:
            self.get('/api/v1/meeting/transcript')
        self.assertEqual(error.exception.code, 503)
        report['source_generated_at_utc'] = original_source
        publish_report(report, target)
        self.assertEqual(self.get('/api/v1/meeting/transcript')[0], 200)

        # A missing configured file must not silently fall back to another report.
        with patch.object(v28, 'MEETING_TRANSCRIPT_PATH', target):
            self.server.RequestHandlerClass = v28.make_handler(
                self.history, meeting_transcript_path=target.with_name('absent.json'))
            with self.assertRaises(HTTPError) as error:
                self.get('/api/v1/meeting/transcript')
            self.assertEqual(error.exception.code, 503)
        target.write_text('{"orders_enabled": true}', encoding='utf-8')
        self.server.RequestHandlerClass = v28.make_handler(
            self.history, meeting_transcript_path=target)
        with self.assertRaises(HTTPError) as error:
            self.get('/api/v1/meeting/transcript')
        self.assertEqual(error.exception.code, 503)

    def test_cli_selected_transcript_from_another_working_directory(self):
        self.check_cli_selected_transcript(use_session=False)

    def test_cli_meeting_session_from_another_working_directory(self):
        self.check_cli_selected_transcript(use_session=True)

    def check_cli_selected_transcript(self, *, use_session):
        from ai_meeting_runtime import publish_report, run_meeting
        from test_ai_meeting_runtime import Fixture
        from test_v240_provider_transport_preflight import request, NOW
        report = run_meeting(request(), Fixture(), clock=lambda: NOW)
        now = datetime.now(timezone.utc)
        for field, minutes in [('source_generated_at_utc', 5),
                               ('started_at_utc', 4), ('generated_at_utc', 3)]:
            report[field] = (now - timedelta(minutes=minutes)).isoformat()
        report['market_source'] = 'BYBIT_USDT_PERPETUAL_5M'
        report['workflow_execution_id'] = 'a'*32
        artifact_dir = Path(self.temp.name)/'meeting session with spaces' if use_session else Path(self.temp.name)
        artifact_dir.mkdir(exist_ok=True)
        target = artifact_dir / ('latest.json' if use_session else 'custom completed meeting.json')
        publish_report(report, target)
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        from ai_meeting_workflow_status import write_status
        status_file = artifact_dir/('workflow_status.json' if use_session else 'selected workflow status.json')
        event = {'version': 'MEETING_WORKFLOW_EVENT_1', 'event': 'STAGE_STARTED',
                 'workflow_stage': 'PREPARATION', 'status': 'RUNNING'}
        write_status(event, status_file, 'a'*32)
        execution_id = 'a'*32
        if use_session:
            import io
            import os
            from contextlib import redirect_stdout, redirect_stderr
            from ai_meeting_workflow import main as workflow_main
            from test_v233_agent_research_runtime import source
            brief = Path(self.temp.name)/'source brief.json'
            payload = source()
            payload.update(source_generated_at_utc=(now-timedelta(minutes=10)).isoformat(),
                           generated_at_utc=(now-timedelta(minutes=5)).isoformat(),
                           market_source='BYBIT_USDT_PERPETUAL_5M')
            brief.write_text(json.dumps(payload))
            output, errors = io.StringIO(), io.StringIO()
            arguments = ['workflow', str(brief), '--meeting-session', str(artifact_dir),
                         '--model', 'test-model', '--enable-live', '--json']
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'fixture-session-key'}), patch('sys.argv', arguments):
                with redirect_stdout(output), redirect_stderr(errors), patch('ai_meeting_workflow.OpenAIProvider', return_value=Fixture()):
                    self.assertEqual(workflow_main(), 0)
            result = json.loads(output.getvalue())
            execution_id = result['execution_id']
            self.assertEqual(result['model_calls_performed'], 0)
            self.assertNotIn('fixture-session-key', output.getvalue()+errors.getvalue())

        command = [sys.executable, str(Path(v28.__file__).resolve()),
                   '--port', str(port), '--history', str(self.history),
                   '--meeting-transcript', str(target), '--meeting-status', str(status_file),
                   '--meeting-execution-id', 'a'*32]
        if use_session:
            command = command[:command.index('--meeting-transcript')] + ['--meeting-session', str(artifact_dir)]
        process = subprocess.Popen(command, cwd=self.temp.name,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        base = 'http://127.0.0.1:' + str(port)
        try:
            deadline = time.monotonic() + 10
            while True:
                if process.poll() is not None:
                    self.fail('Dashboard CLI exited before startup')
                try:
                    with urlopen(base + '/health', timeout=1) as response:
                        self.assertEqual(response.status, 200)
                    break
                except URLError:
                    if time.monotonic() >= deadline:
                        self.fail('Dashboard CLI startup timed out')
                    time.sleep(0.05)
            with urlopen(base + '/api/v1/meeting/transcript', timeout=3) as response:
                payload = json.load(response)
            self.assertEqual(len(payload['transcript']), 7)
            self.assertFalse(payload['orders_enabled'])
            self.assertFalse(payload['model_inference_performed'])
            with urlopen(base + '/office3d', timeout=3) as response:
                self.assertIn(b'ai-meeting-panel', response.read())
            with urlopen(base + '/api/v1/meeting/workflow-status', timeout=3) as response:
                self.assertEqual(json.load(response)['snapshot']['execution_id'], execution_id)
            write_status(event, status_file, 'b'*32)
            with self.assertRaises(HTTPError) as error:
                urlopen(base + '/api/v1/meeting/workflow-status', timeout=3)
            self.assertEqual(error.exception.code, 409)
            self.assertEqual(json.load(error.exception)['error'], 'workflow_execution_mismatch')
            target.unlink()
            with self.assertRaises(HTTPError) as error:
                urlopen(base + '/api/v1/meeting/transcript', timeout=3)
            self.assertEqual(error.exception.code, 503)
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            process.stderr.close()

    def test_workflow_status_endpoint_is_read_only_and_fails_closed(self):
        from ai_meeting_workflow_status import write_status
        with self.assertRaises(HTTPError) as error:
            self.get('/api/v1/meeting/workflow-status')
        self.assertEqual(error.exception.code, 404)
        target = Path(self.temp.name) / 'workflow-status.json'
        event = {'version': 'MEETING_WORKFLOW_EVENT_1', 'event': 'STAGE_STARTED',
                 'workflow_stage': 'PREPARATION', 'status': 'RUNNING'}
        write_status(event, target, 'a'*32)
        self.server.RequestHandlerClass = v28.make_handler(self.history, meeting_status_path=target)
        with patch('ai_meeting_runtime.OpenAIProvider.complete', side_effect=AssertionError('model call')) as provider:
            status, payload = self.get('/api/v1/meeting/workflow-status')
        provider.assert_not_called()
        self.assertEqual(status, 200)
        self.assertEqual(payload['snapshot']['status'], 'RUNNING')
        self.assertTrue(payload['read_only'])
        self.assertFalse(payload['process_liveness_verified'])
        self.assertFalse(payload['orders_enabled'])
        progress = {'version': 'MEETING_WORKFLOW_EVENT_2', 'event': 'MODEL_PROGRESS',
                    'workflow_stage': 'INFERENCE', 'status': 'RUNNING', 'agent': 'ATLAS',
                    'phase': 'ANALYSIS', 'attempted_calls': 1, 'validated_responses': 0}
        write_status(progress, target, 'a'*32)
        _, payload = self.get('/api/v1/meeting/workflow-status')
        self.assertEqual(payload['snapshot']['agent'], 'ATLAS')
        self.assertEqual(payload['snapshot']['validated_responses'], 0)
        write_status(event, target, 'a'*32)
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base + '/api/v1/meeting/workflow-status', data=b'{}', method='POST'), timeout=3)
        self.assertEqual(error.exception.code, 405)
        write_status(event, target, 'a'*32, now=datetime.now(timezone.utc)-timedelta(minutes=6))
        with self.assertRaises(HTTPError) as error:
            self.get('/api/v1/meeting/workflow-status')
        self.assertEqual(error.exception.code, 503)
        target.write_text('{"private": "never expose"}')
        with self.assertRaises(HTTPError) as error:
            self.get('/api/v1/meeting/workflow-status')
        self.assertEqual(error.exception.code, 503)
        self.assertNotIn('never expose', error.exception.read().decode())

    def test_fixture_workflow_events_reach_pinned_api_and_completed_transcript(self):
        import os
        from ai_meeting_workflow import run_workflow
        from ai_meeting_workflow_status import write_status, WorkflowStatusRecorder
        from test_ai_meeting_runtime import Fixture
        from test_v233_agent_research_runtime import source
        brief = Path(self.temp.name)/'brief.json'
        transcript = Path(self.temp.name)/'meeting-output.json'
        status_file = Path(self.temp.name)/'workflow-status.json'
        payload = source()
        now = datetime.now(timezone.utc)
        payload.update(source_generated_at_utc=(now-timedelta(minutes=10)).isoformat(),
                       generated_at_utc=(now-timedelta(minutes=5)).isoformat(),
                       market_source='BYBIT_USDT_PERPETUAL_5M')
        brief.write_text(json.dumps(payload), encoding='utf-8')
        execution_id = 'c'*32
        self.server.RequestHandlerClass = v28.make_handler(
            self.history, meeting_transcript_path=transcript,
            meeting_status_path=status_file, meeting_execution_id=execution_id)
        observed = []
        recorder = WorkflowStatusRecorder(status_file, execution_id)
        def record(event):
            recorder(event)
            status, view = self.get('/api/v1/meeting/workflow-status')
            self.assertEqual(status, 200)
            self.assertFalse(view['orders_enabled'])
            self.assertEqual(view['snapshot']['execution_id'], execution_id)
            observed.append(view['snapshot'])
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-workflow-key'}):
            with patch('ai_meeting_workflow.OpenAIProvider', return_value=Fixture()):
                result = run_workflow(brief, transcript, 'test-model', enable_live=True, on_event=record, execution_id=execution_id)
        self.assertEqual(result['status'], 'COMPLETED')
        self.assertEqual(result['model_calls_performed'], 0)
        progress = [item for item in observed if item['event'] == 'MODEL_PROGRESS']
        self.assertEqual(len(progress), 14)
        self.assertEqual(progress[-1]['agent'], 'COMMANDER')
        self.assertEqual(progress[-1]['validated_responses'], 7)
        self.assertEqual(observed[-1]['status'], 'COMPLETED')
        self.assertEqual(recorder.counts, (7, 7))
        _, completed = self.get('/api/v1/meeting/transcript')
        self.assertEqual(len(completed['transcript']), 7)
        self.assertFalse(completed['model_inference_performed'])
        self.assertFalse(completed['orders_enabled'])
        self.assertEqual(completed['workflow_execution_id'], execution_id)
        raw_report = json.loads(transcript.read_text())
        for invalid_id in ['d'*32, None, 'not-an-id']:
            altered = dict(raw_report)
            if invalid_id is None:
                altered.pop('workflow_execution_id')
            else:
                altered['workflow_execution_id'] = invalid_id
            transcript.write_text(json.dumps(altered))
            with self.assertRaises(HTTPError) as error:
                self.get('/api/v1/meeting/transcript')
            self.assertEqual(error.exception.code, 503 if invalid_id == 'not-an-id' else 409)
            if invalid_id != 'not-an-id':
                self.assertEqual(json.load(error.exception)['error'], 'meeting_execution_mismatch')
        transcript.write_text(json.dumps(raw_report))
        self.assertEqual(self.get('/api/v1/meeting/transcript')[0], 200)
        # A new run overwriting this same path must not be mistaken for the pinned run.
        event = {'version': 'MEETING_WORKFLOW_EVENT_1', 'event': 'STAGE_STARTED',
                 'workflow_stage': 'PREPARATION', 'status': 'RUNNING'}
        write_status(event, status_file, 'd'*32)
        with self.assertRaises(HTTPError) as error:
            self.get('/api/v1/meeting/workflow-status')
        self.assertEqual(error.exception.code, 409)
        self.assertEqual(json.load(error.exception)['error'], 'workflow_execution_mismatch')
        write_status(event, status_file, 'd'*32, now=datetime.now(timezone.utc)-timedelta(minutes=6))
        with self.assertRaises(HTTPError) as error:
            self.get('/api/v1/meeting/workflow-status')
        self.assertEqual(error.exception.code, 503)
        write_status(event, status_file, execution_id)
        self.assertEqual(self.get('/api/v1/meeting/workflow-status')[0], 200)
        self.assertNotIn('offline-workflow-key', status_file.read_text()+transcript.read_text())

    def test_workflow_execution_selection_rejects_invalid_configuration(self):
        for execution_id in ['', 'A'*32, 'a'*31, '../private', True]:
            with self.subTest(execution_id=execution_id), self.assertRaises(ValueError):
                v28.make_handler(self.history, meeting_status_path='status.json', meeting_execution_id=execution_id)
        with self.assertRaises(ValueError):
            v28.make_handler(self.history, meeting_execution_id='a'*32)
        result = subprocess.run([sys.executable, str(Path(v28.__file__).resolve()),
                                 '--meeting-execution-id', 'invalid'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('requires --meeting-status', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_cli_meeting_session_rejects_stale_invalid_and_conflicting_options(self):
        from ai_meeting_workflow_status import write_status
        session = Path(self.temp.name)/'session with spaces'
        session.mkdir()
        status_file = session/'workflow_status.json'
        event = {'version': 'MEETING_WORKFLOW_EVENT_1', 'event': 'STAGE_STARTED',
                 'workflow_stage': 'PREPARATION', 'status': 'RUNNING'}
        base = [sys.executable, str(Path(v28.__file__).resolve()), '--meeting-session', str(session)]
        for mode in ('missing', 'malformed', 'stale', 'conflict'):
            if mode == 'malformed':
                status_file.write_text('private invalid content')
            elif mode == 'stale':
                write_status(event, status_file, 'a'*32, now=datetime.now(timezone.utc)-timedelta(minutes=6))
            elif mode == 'conflict':
                write_status(event, status_file, 'a'*32)
            command = base + (['--meeting-execution-id', 'a'*32] if mode == 'conflict' else [])
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2, mode)
            self.assertNotIn('Traceback', result.stderr)
            self.assertNotIn('private invalid content', result.stderr)
        # Resolving/serving a session must not alter its saved state.
        self.assertEqual(json.loads(status_file.read_text())['execution_id'], 'a'*32)

    def test_unknown_route(self):
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/orders")
        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
