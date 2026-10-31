import unittest
from datetime import datetime, timezone, timedelta
from agent_research_runtime_v233 import build_research
from agent_handoff_audit_v234 import compile_handoff
from research_consistency_review_v235 import review
NOW=datetime(2026,10,31,6,tzinfo=timezone.utc)
def handoff():
    stamp=(NOW-timedelta(minutes=10)).isoformat()
    report={"version":"V229.0","report_type":"DETERMINISTIC_COMMANDER_RESEARCH_BRIEF",
    "research_only":True,"orders_enabled":False,"realtime":False,
    "ai_agents_running":False,"trade_signals_available":False,"backtest_verified":False,
    "commander":{"status":"COMPILED_NOT_AI"},"source_generated_at_utc":stamp,
    "generated_at_utc":(NOW-timedelta(minutes=5)).isoformat(),
    "markets":[{"symbol":s,"trend_observation":t,"volume_ratio_20":1.5,
    "risk_status":"NO_TRADE_AUTHORIZATION","research_conclusion":"DESCRIPTIVE_ONLY"}
    for s,t in zip(("BTCUSDT","ETHUSDT","SOLUSDT"),
    ("SMA50_ABOVE_SMA200","SMA50_BELOW_SMA200","SMA_EQUAL"))]}
    return compile_handoff(build_research(report,NOW-timedelta(minutes=2)),NOW-timedelta(minutes=1))
class ReviewTests(unittest.TestCase):
    def test_detects_descriptive_cross_symbol_differences(self):
        result=review(handoff(),NOW)
        self.assertTrue(result["commander"]["trend_classifications_differ"])
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["model_inference_performed"])
        self.assertEqual(result["commander"]["trade_authorization"],"DENIED")
    def test_rejects_unsafe_guardian(self):
        data=handoff();data["events"][2]["observation"]["authorization"]="ALLOWED"
        with self.assertRaises(ValueError):review(data,NOW)
    def test_rejects_duplicate_agent(self):
        data=handoff();data["events"][1]["agent"]="ATLAS"
        with self.assertRaises(ValueError):review(data,NOW)
    def test_rejects_stale_and_unsafe_flags(self):
        data=handoff();data["source_generated_at_utc"]=(NOW-timedelta(hours=9)).isoformat()
        with self.assertRaises(ValueError):review(data,NOW)
        data=handoff();data["orders_enabled"]=True
        with self.assertRaises(ValueError):review(data,NOW)
if __name__=="__main__":unittest.main()
