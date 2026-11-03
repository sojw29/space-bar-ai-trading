"""V28 local API tests: ephemeral loopback HTTP, no external network."""
import csv
from datetime import datetime, timedelta, timezone
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
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
        from ai_meeting_runtime import run_meeting
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
        target.write_text(json.dumps(report), encoding="utf-8")
        with patch.object(v28, "MEETING_TRANSCRIPT_PATH", target):
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
const elements={};
for(const id of ['ai-meeting-status','ai-meeting-rows','ai-meeting-refresh'])
 elements[id]={children:[],disabled:false,addEventListener(){},replaceChildren(...items){this.children=items}};
let requested=null;
const document={hidden:false,getElementById:id=>elements[id],addEventListener:()=>{},
 createElement:()=>({style:{},set innerHTML(_){throw Error('unsafe HTML')}})};
vm.runInNewContext(data.script,{document,Date,setInterval:()=>{},
 fetch:async url=>{requested=url;return {ok:true,text:async()=>JSON.stringify(data.payload)}}});
setImmediate(()=>{
 try{
  assert.equal(requested,'/api/v1/meeting/transcript');
  assert.equal(elements['ai-meeting-rows'].children.length,7);
  assert.match(elements['ai-meeting-status'].textContent,/실제 AI 실행 아님/);
  assert.ok(elements['ai-meeting-rows'].children.every(x=>typeof x.textContent==='string'));
 }catch(e){console.error(e);process.exitCode=1}
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

    def test_unknown_route(self):
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/orders")
        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
