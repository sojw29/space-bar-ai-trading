import unittest
from datetime import datetime, timezone, timedelta
from model_adapter_contract_v236 import build_adapter_requests
NOW=datetime(2026,10,31,6,tzinfo=timezone.utc)
def source():
 return {"version":"V235.0","review_type":"DETERMINISTIC_CROSS_SYMBOL_CONSISTENCY",
 "research_only":True,"orders_enabled":False,"ai_agents_running":False,
 "model_inference_performed":False,"trade_signals_available":False,
 "source_generated_at_utc":(NOW-timedelta(minutes=10)).isoformat(),
 "generated_at_utc":(NOW-timedelta(minutes=5)).isoformat(),
 "commander":{"status":"DESCRIPTIVE_REVIEW_ONLY","trade_authorization":"DENIED",
 "trend_classifications_differ":True,"volume_data_availability_differs":False},
 "markets":[{"symbol":s,"sma_relationship":"SMA50_ABOVE_SMA200",
 "volume_ratio_20":1.5,"guardian":"DENIED","review_status":"DESCRIPTIVE_ONLY"}
 for s in ("BTCUSDT","ETHUSDT","SOLUSDT")]}
class AdapterTests(unittest.TestCase):
 def test_creates_four_unexecuted_requests(self):
  data=build_adapter_requests(source(),NOW)
  self.assertEqual([r["agent"] for r in data["requests"]],["ATLAS","QUANT","GUARDIAN","COMMANDER"])
  self.assertFalse(data["model_inference_performed"])
  self.assertFalse(data["orders_enabled"])
  self.assertFalse(data["network_access_required"])
  self.assertTrue(all(r["trade_authorization"]=="DENIED" for r in data["requests"]))
 def test_rejects_unsafe_source(self):
  for field in ("orders_enabled","ai_agents_running","model_inference_performed","trade_signals_available"):
   data=source();data[field]=True
   with self.subTest(field=field),self.assertRaises(ValueError):build_adapter_requests(data,NOW)
 def test_rejects_bad_market(self):
  data=source();data["markets"][0]["guardian"]="ALLOWED"
  with self.assertRaises(ValueError):build_adapter_requests(data,NOW)
  data=source();data["markets"][1]["symbol"]="BTCUSDT"
  with self.assertRaises(ValueError):build_adapter_requests(data,NOW)
 def test_rejects_stale(self):
  data=source();data["source_generated_at_utc"]=(NOW-timedelta(hours=9)).isoformat()
  with self.assertRaises(ValueError):build_adapter_requests(data,NOW)
if __name__=="__main__":unittest.main()
