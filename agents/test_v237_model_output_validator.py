import hashlib
import json
import unittest
from datetime import datetime, timezone, timedelta
from model_adapter_contract_v236 import build_adapter_requests
from model_output_validator_v237 import validate_outputs, canonical, AGENTS
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
def mock(req):
 return {"version":"V237.MOCK.1","source":"OFFLINE_FIXTURE_ONLY",
 "request_sha256":hashlib.sha256(canonical(req)).hexdigest(),
 "responses":[{"agent":a,"status":"OBSERVATION","summary":"Descriptive market data only.",
 "trade_authorization":"DENIED"} for a in AGENTS]}
class OutputTests(unittest.TestCase):
 def test_accepts_safe_mock_with_explicit_no_execution(self):
  req=request();data=validate_outputs(req,mock(req),NOW)
  self.assertEqual(len(data["responses"]),4)
  self.assertFalse(data["model_inference_performed"])
  self.assertFalse(data["validated_for_trading"])
 def test_rejects_unbound_output(self):
  req=request();data=mock(req);data["request_sha256"]="0"*64
  with self.assertRaises(ValueError):validate_outputs(req,data,NOW)
 def test_rejects_trade_language(self):
  for value in ("BUY BTC now","레버리지 50배", "Enter long", "손절 설정"):
   req=request();data=mock(req);data["responses"][0]["summary"]=value
   with self.subTest(value=value),self.assertRaises(ValueError):validate_outputs(req,data,NOW)
 def test_rejects_extra_fields_and_unsafe_flags(self):
  req=request();data=mock(req);data["responses"][0]["order_size"]=100
  with self.assertRaises(ValueError):validate_outputs(req,data,NOW)
  req=request();req["orders_enabled"]=True
  with self.assertRaises(ValueError):validate_outputs(req,mock(req),NOW)
 def test_rejects_stale(self):
  req=request();req["source_generated_at_utc"]=(NOW-timedelta(hours=9)).isoformat()
  with self.assertRaises(ValueError):validate_outputs(req,mock(req),NOW)
if __name__=="__main__":unittest.main()
