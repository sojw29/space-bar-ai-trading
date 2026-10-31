import unittest
from datetime import datetime, timezone, timedelta
from pipeline_regression_matrix_v243 import evaluate_matrix
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
class MatrixTests(unittest.TestCase):
 def test_nine_unsafe_mutations_are_rejected(self):
  result=evaluate_matrix(source(),NOW)
  self.assertEqual(result["rejected_count"],9)
  self.assertTrue(all(row["status"]=="REJECTED_AS_EXPECTED" for row in result["scenarios"]))
  self.assertFalse(result["orders_enabled"])
  self.assertFalse(result["network_enabled"])
 def test_deterministic_result(self):
  self.assertEqual(evaluate_matrix(source(),NOW),evaluate_matrix(source(),NOW))
 def test_invalid_baseline_is_not_reported_as_success(self):
  data=source();data["orders_enabled"]=True
  with self.assertRaises(ValueError):evaluate_matrix(data,NOW)
 def test_source_is_not_mutated(self):
  data=source();before=data["markets"][0]["volume_ratio_20"]
  evaluate_matrix(data,NOW)
  self.assertEqual(data["markets"][0]["volume_ratio_20"],before)
if __name__=="__main__":unittest.main()
