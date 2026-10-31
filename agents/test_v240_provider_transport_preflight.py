import unittest
from datetime import datetime, timezone, timedelta
from model_adapter_contract_v236 import build_adapter_requests
from provider_transport_preflight_v240 import preflight, ProviderNotEnabled
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
class PreflightTests(unittest.TestCase):
 def test_requires_explicit_dry_run(self):
  with self.assertRaises(ProviderNotEnabled):preflight(request(),now=NOW)
 def test_safe_preflight_has_no_transport(self):
  result=preflight(request(),dry_run=True,now=NOW)
  self.assertEqual(result["status"],"VALIDATED_NOT_DISPATCHED")
  self.assertFalse(result["network_enabled"])
  self.assertFalse(result["model_inference_performed"])
  self.assertFalse(result["orders_enabled"])
  self.assertEqual(result["request_count"],4)
 def test_rejects_divergent_facts(self):
  req=request();req["requests"][2]["facts"]["markets"][0]["volume_ratio_20"]=5
  with self.assertRaises(ValueError):preflight(req,dry_run=True,now=NOW)
 def test_rejects_unsafe_flags(self):
  for key in ("orders_enabled","model_inference_performed","network_access_required"):
   req=request();req[key]=True
   with self.subTest(key=key),self.assertRaises(ValueError):preflight(req,dry_run=True,now=NOW)
 def test_rejects_stale_source(self):
  req=request();req["source_generated_at_utc"]=(NOW-timedelta(hours=9)).isoformat()
  with self.assertRaises(ValueError):preflight(req,dry_run=True,now=NOW)
if __name__=="__main__":unittest.main()
