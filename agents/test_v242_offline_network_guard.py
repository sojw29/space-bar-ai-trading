import socket
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from offline_network_guard_v242 import network_guard, run_guarded_pipeline, UnexpectedNetworkAccess
from model_adapter_contract_v236 import build_adapter_requests
from provider_transport_preflight_v240 import preflight

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
def adapter_source():
 return {"version":"V235.0","review_type":"DETERMINISTIC_CROSS_SYMBOL_CONSISTENCY",
 "research_only":True,"orders_enabled":False,"ai_agents_running":False,
 "model_inference_performed":False,"trade_signals_available":False,
 "source_generated_at_utc":(NOW-timedelta(minutes=10)).isoformat(),
 "generated_at_utc":(NOW-timedelta(minutes=5)).isoformat(),
 "commander":{"status":"DESCRIPTIVE_REVIEW_ONLY","trade_authorization":"DENIED",
 "trend_classifications_differ":False,"volume_data_availability_differs":False},
 "markets":[{"symbol":s,"sma_relationship":"SMA50_ABOVE_SMA200",
 "volume_ratio_20":1.5,"guardian":"DENIED","review_status":"DESCRIPTIVE_ONLY"}
 for s in ("BTCUSDT","ETHUSDT","SOLUSDT")]}
class GuardrailTests(unittest.TestCase):
 def test_offline_integration_passes_with_network_blocked(self):
  result=run_guarded_pipeline(source(),NOW)
  self.assertFalse(result["network_enabled"])
  self.assertFalse(result["orders_enabled"])
  self.assertEqual(len(result["steps"]),6)
 def test_network_connect_is_denied_and_restored(self):
  original=socket.socket.connect
  with network_guard():
   with self.assertRaises(UnexpectedNetworkAccess):
    socket.socket().connect(("127.0.0.1",80))
  self.assertIs(socket.socket.connect,original)
 def test_network_create_connection_denied(self):
  with network_guard():
   with self.assertRaises(UnexpectedNetworkAccess):
    socket.create_connection(("127.0.0.1",80))
 def test_independent_agent_facts_and_preflight_rejection(self):
  bundle=build_adapter_requests(adapter_source(),NOW-timedelta(minutes=1))
  before=bundle["requests"][0]["facts"]["markets"][0]["volume_ratio_20"]
  bundle["requests"][2]["facts"]["markets"][0]["volume_ratio_20"]=5
  self.assertEqual(bundle["requests"][0]["facts"]["markets"][0]["volume_ratio_20"],before)
  with self.assertRaises(ValueError):preflight(bundle,dry_run=True,now=NOW)
 def test_stale_pipeline_fails_closed(self):
  data=source();data["source_generated_at_utc"]=(NOW-timedelta(hours=9)).isoformat()
  with self.assertRaises(ValueError):run_guarded_pipeline(data,NOW)
if __name__=="__main__":unittest.main()
