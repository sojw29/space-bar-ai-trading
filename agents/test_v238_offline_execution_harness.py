import unittest
from datetime import datetime, timezone, timedelta
from model_adapter_contract_v236 import build_adapter_requests
from offline_model_execution_harness_v238 import execute_offline_fixture
NOW=datetime(2026,10,31,6,tzinfo=timezone.utc)
def request():
 return build_adapter_requests({"version":"V235.0","review_type":"DETERMINISTIC_CROSS_SYMBOL_CONSISTENCY",
 "research_only":True,"orders_enabled":False,"ai_agents_running":False,
 "model_inference_performed":False,"trade_signals_available":False,
 "source_generated_at_utc":(NOW-timedelta(minutes=10)).isoformat(),
 "generated_at_utc":(NOW-timedelta(minutes=5)).isoformat(),
 "commander":{"status":"DESCRIPTIVE_REVIEW_ONLY","trade_authorization":"DENIED",
 "trend_classifications_differ":False,"volume_data_availability_differs":False},
 "markets":[{"symbol":s,"sma_relationship":"SMA50_ABOVE_SMA200",
 "volume_ratio_20":1.5,"guardian":"DENIED","review_status":"DESCRIPTIVE_ONLY"}
 for s in ("BTCUSDT","ETHUSDT","SOLUSDT")]},NOW-timedelta(minutes=1))
class HarnessTests(unittest.TestCase):
 def test_fixture_round_trip(self):
  result=execute_offline_fixture(request(),NOW)
  self.assertEqual(len(result["responses"]),4)
  self.assertFalse(result["model_inference_performed"])
  self.assertFalse(result["orders_enabled"])
  self.assertFalse(result["validated_for_trading"])
 def test_deterministic_mock(self):
  req=request()
  self.assertEqual(execute_offline_fixture(req,NOW),execute_offline_fixture(req,NOW))
 def test_rejects_unsafe_input(self):
  req=request();req["orders_enabled"]=True
  with self.assertRaises(ValueError):execute_offline_fixture(req,NOW)
 def test_rejects_stale(self):
  req=request();req["source_generated_at_utc"]=(NOW-timedelta(hours=9)).isoformat()
  with self.assertRaises(ValueError):execute_offline_fixture(req,NOW)
if __name__=="__main__":unittest.main()
