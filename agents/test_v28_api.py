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
        script = html.split('id="ai-meeting-panel"', 1)[1].split("<script>", 1)[1].split("</script>", 1)[0]
        harness = r"""
const assert=require('node:assert/strict'),vm=require('node:vm');
const data=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const makeElement=()=>({
 children:[],disabled:false,hidden:false,style:{},attrs:{},events:{},
 focus(){this.focused=true},scrollIntoView(){this.scrolled=true},
 addEventListener(name,fn){this.events[name]=fn},
 setAttribute(name,value){this.attrs[name]=value},
 replaceChildren(...items){this.children=items},
 set innerHTML(_){throw Error('unsafe HTML')}
});
const elements={};
for(const id of ['ai-meeting-panel','ai-meeting-summary','ai-meeting-shortcut','ai-meeting-shortcut-status',
 'ai-meeting-status','ai-meeting-rows','ai-meeting-refresh',
 'ai-meeting-timeline','ai-meeting-linked','ai-meeting-decision','ai-meeting-connection-label'])
 elements[id]=makeElement();
let requested=null,failRequest=false,requestCount=0,holdResponse=null;
const documentEvents={},windowEvents={};
const window={addEventListener:(name,fn)=>{windowEvents[name]=fn}};
const document={hidden:false,getElementById:id=>elements[id],addEventListener:(name,fn)=>{documentEvents[name]=fn},
 createElement:makeElement};
const callbacks=[],timeouts=new Map();
let timeoutId=0,timeoutPhase=null,bodyFault=null,httpStatus=null,networkFault=false;
let now=Date.now();
class Clock extends Date{static now(){return now}}
vm.runInNewContext(data.script,{document,window,Date:Clock,AbortController,
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
  for(const [code,message] of [[404,/API 경로/],[401,/접근이 거부/],[403,/접근이 거부/],
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
        from ai_meeting_runtime import publish_report, run_meeting
        from test_ai_meeting_runtime import Fixture
        from test_v240_provider_transport_preflight import request, NOW
        report = run_meeting(request(), Fixture(), clock=lambda: NOW)
        now = datetime.now(timezone.utc)
        for field, minutes in [('source_generated_at_utc', 5),
                               ('started_at_utc', 4), ('generated_at_utc', 3)]:
            report[field] = (now - timedelta(minutes=minutes)).isoformat()
        report['market_source'] = 'BYBIT_USDT_PERPETUAL_5M'
        target = Path(self.temp.name) / 'custom completed meeting.json'
        publish_report(report, target)
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        command = [sys.executable, str(Path(v28.__file__).resolve()),
                   '--port', str(port), '--history', str(self.history),
                   '--meeting-transcript', str(target)]
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

    def test_unknown_route(self):
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/orders")
        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
