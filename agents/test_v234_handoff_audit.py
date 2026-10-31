import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from agent_research_runtime_v233 import build_research
from agent_handoff_audit_v234 import compile_handoff
NOW=datetime(2026,10,31,6,tzinfo=timezone.utc)
def source():
    stamp=(NOW-timedelta(minutes=10)).isoformat()
    report=(NOW-timedelta(minutes=5)).isoformat()
    return {"version":"V229.0","report_type":"DETERMINISTIC_COMMANDER_RESEARCH_BRIEF",
    "research_only":True,"orders_enabled":False,"realtime":False,
    "ai_agents_running":False,"trade_signals_available":False,"backtest_verified":False,
    "commander":{"status":"COMPILED_NOT_AI"},"source_generated_at_utc":stamp,
    "generated_at_utc":report,"markets":[
    {"symbol":s,"trend_observation":"SMA50_ABOVE_SMA200",
    "volume_ratio_20":1.5,"risk_status":"NO_TRADE_AUTHORIZATION",
    "research_conclusion":"DESCRIPTIVE_ONLY"} for s in ("BTCUSDT","ETHUSDT","SOLUSDT")]}
def runtime():
    return build_research(source(),NOW-timedelta(minutes=1))
class HandoffTests(unittest.TestCase):
    def test_twelve_events_and_deterministic_digest(self):
        data=runtime()
        a=compile_handoff(data,NOW)
        b=compile_handoff(data,NOW)
        self.assertEqual(a["event_count"],12)
        self.assertEqual(a["input_event_sha256"],b["input_event_sha256"])
        self.assertFalse(a["orders_enabled"])
        self.assertFalse(a["model_inference_performed"])
        self.assertEqual([x["agent"] for x in a["events"][:4]],
                         ["ATLAS","QUANT","GUARDIAN","COMMANDER"])
    def test_rejects_unsafe_flags(self):
        for key in ("orders_enabled","ai_agents_running","model_inference_performed","trade_signals_available"):
            data=runtime();data[key]=True
            with self.subTest(key=key),self.assertRaises(ValueError):compile_handoff(data,NOW)
    def test_rejects_unsafe_agents(self):
        for agent,key,value in (("GUARDIAN","orders_enabled",True),
                                ("COMMANDER","recommendation","BUY"),
                                ("QUANT","volume_ratio_20",float("nan"))):
            data=runtime();data["markets"][0][agent][key]=value
            with self.subTest(agent=agent),self.assertRaises(ValueError):compile_handoff(data,NOW)
    def test_cli_collision_preserves_invalid_source(self):
        from agent_handoff_audit_v234 import main
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "untrusted.json"
            path.write_text('{"bad": true}', encoding="utf-8")
            with patch("sys.argv", ["v234", str(path), str(path)]):
                with self.assertRaisesRegex(ValueError, "SOURCE_DESTINATION_COLLISION"):
                    main()
            self.assertEqual(path.read_text(encoding="utf-8"), '{"bad": true}')

    def test_cli_failure_removes_stale_distinct_output(self):
        from agent_handoff_audit_v234 import main
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "untrusted.json"
            target_path = Path(directory) / "old.json"
            source_path.write_text('{"bad": true}', encoding="utf-8")
            target_path.write_text('{"stale": true}', encoding="utf-8")
            with patch("sys.argv", ["v234", str(source_path), str(target_path)]):
                with self.assertRaises(ValueError):
                    main()
            self.assertFalse(target_path.exists())
            self.assertTrue(source_path.exists())

    def test_rejects_stale_or_future_data(self):
        data=runtime();data["source_generated_at_utc"]=(NOW-timedelta(hours=9)).isoformat()
        with self.assertRaises(ValueError):compile_handoff(data,NOW)
        data=runtime();data["generated_at_utc"]=(NOW+timedelta(minutes=1)).isoformat()
        with self.assertRaises(ValueError):compile_handoff(data,NOW)
if __name__=="__main__":unittest.main()
