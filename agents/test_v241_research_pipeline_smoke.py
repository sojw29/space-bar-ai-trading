import unittest
from datetime import datetime, timezone, timedelta
from research_pipeline_smoke_v241 import run_pipeline
NOW=datetime(2026,10,31,6,tzinfo=timezone.utc)
def source():
 return {"version":"V229.0","report_type":"DETERMINISTIC_COMMANDER_RESEARCH_BRIEF",
 "research_only":True,"orders_enabled":False,"realtime":False,
 "ai_agents_running":False,"trade_signals_available":False,"backtest_verified":False,
 "commander":{"status":"COMPILED_NOT_AI"},
 "source_generated_at_utc":(NOW-timedelta(minutes=10)).isoformat(),
 "generated_at_utc":(NOW-timedelta(minutes=5)).isoformat(),
 "markets":[{"symbol":s,"trend_observation":"SMA50_ABOVE_SMA200",
 "volume_ratio_20":1.5,"risk_status":"NO_TRADE_AUTHORIZATION",
 "research_conclusion":"DESCRIPTIVE_ONLY"}
 for s in ("BTCUSDT","ETHUSDT","SOLUSDT")]}
class PipelineTests(unittest.TestCase):
 def test_full_pipeline_is_offline_and_no_trade(self):
  result=run_pipeline(source(),NOW)
  self.assertEqual(len(result["steps"]),6)
  self.assertEqual(result["steps"][1]["event_count"],12)
  self.assertFalse(result["orders_enabled"])
  self.assertFalse(result["network_enabled"])
  self.assertFalse(result["model_inference_performed"])
  self.assertFalse(result["validated_for_trading"])
 def test_deterministic_pipeline(self):
  self.assertEqual(run_pipeline(source(),NOW),run_pipeline(source(),NOW))
 def test_unsafe_source_fails_closed(self):
  data=source();data["orders_enabled"]=True
  with self.assertRaises(ValueError):run_pipeline(data,NOW)
 def test_stale_source_fails_closed(self):
  data=source();data["source_generated_at_utc"]=(NOW-timedelta(hours=9)).isoformat()
  with self.assertRaises(ValueError):run_pipeline(data,NOW)
 def test_missing_market_fails_closed(self):
  data=source();data["markets"].pop()
  with self.assertRaises(ValueError):run_pipeline(data,NOW)
if __name__=="__main__":unittest.main()
