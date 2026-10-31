import hashlib
import unittest
from datetime import datetime, timezone, timedelta
from model_adapter_contract_v236 import build_adapter_requests
from model_output_validator_v237 import canonical, AGENTS
from provider_boundary_v239 import execute_with_injected_fixture, ProviderDisabledError
NOW=datetime(2026,10,31,6,tzinfo=timezone.utc)
def bundle():
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
def fixture(req):
 return {"version":"V237.MOCK.1","source":"OFFLINE_FIXTURE_ONLY",
 "request_sha256":hashlib.sha256(canonical(req)).hexdigest(),
 "responses":[{"agent":a,"status":"OBSERVATION","summary":"Descriptive observation only.",
 "trade_authorization":"DENIED"} for a in AGENTS]}
class BoundaryTests(unittest.TestCase):
 def test_default_disabled_and_callback_not_called(self):
  calls=[]
  with self.assertRaises(ProviderDisabledError):
   execute_with_injected_fixture(bundle(),lambda req:calls.append(req),now=NOW)
  self.assertEqual(calls,[])
 def test_local_fixture_explicitly_enabled(self):
  result=execute_with_injected_fixture(bundle(),fixture,allow_offline_fixture=True,now=NOW)
  self.assertEqual(len(result["responses"]),4)
  self.assertFalse(result["model_inference_performed"])
  self.assertFalse(result["orders_enabled"])
 def test_unsafe_input_never_calls_fixture(self):
  req=bundle();req["orders_enabled"]=True;calls=[]
  with self.assertRaises(ValueError):
   execute_with_injected_fixture(req,lambda r:calls.append(r),allow_offline_fixture=True,now=NOW)
  self.assertEqual(calls,[])
 def test_unsafe_response_rejected(self):
  def bad(req):
   response=fixture(req);response["responses"][0]["summary"]="BUY now"
   return response
  with self.assertRaises(ValueError):
   execute_with_injected_fixture(bundle(),bad,allow_offline_fixture=True,now=NOW)
if __name__=="__main__":unittest.main()
