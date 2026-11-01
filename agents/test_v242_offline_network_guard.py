import socket
import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

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
  with socket.socket() as sock:
   with network_guard():
    with self.assertRaises(UnexpectedNetworkAccess):
     sock.connect(("127.0.0.1",80))
  self.assertIs(socket.socket.connect,original)
 def test_network_create_connection_denied(self):
  with network_guard():
   with self.assertRaises(UnexpectedNetworkAccess):
    socket.create_connection(("127.0.0.1",80))
 def test_udp_sendto_is_denied_and_restored(self):
  original=socket.socket.sendto
  with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
   with network_guard():
    with self.assertRaises(UnexpectedNetworkAccess):
     sock.sendto(b"no-network",("127.0.0.1",80))
  self.assertIs(socket.socket.sendto,original)
 def test_preconnected_socket_send_is_denied(self):
  with socket.socket() as sock:
   with network_guard():
    with self.assertRaises(UnexpectedNetworkAccess):
     sock.send(b"no-network")
    with self.assertRaises(UnexpectedNetworkAccess):
     sock.sendall(b"no-network")
 def test_independent_agent_facts_and_preflight_rejection(self):
  bundle=build_adapter_requests(adapter_source(),NOW-timedelta(minutes=1))
  before=bundle["requests"][0]["facts"]["markets"][0]["volume_ratio_20"]
  bundle["requests"][2]["facts"]["markets"][0]["volume_ratio_20"]=5
  self.assertEqual(bundle["requests"][0]["facts"]["markets"][0]["volume_ratio_20"],before)
  with self.assertRaises(ValueError):preflight(bundle,dry_run=True,now=NOW)
 def test_stale_pipeline_fails_closed(self):
  data=source();data["source_generated_at_utc"]=(NOW-timedelta(hours=9)).isoformat()
  with self.assertRaises(ValueError):run_guarded_pipeline(data,NOW)
 def test_dns_resolution_is_blocked_without_calling_resolver(self):
  calls={
   "getaddrinfo":("example.invalid",443),
   "gethostbyname":("example.invalid",),
   "gethostbyname_ex":("example.invalid",),
   "gethostbyaddr":("192.0.2.1",),
   "getnameinfo":(("192.0.2.1",443),0),
  }
  for name,args in calls.items():
   with self.subTest(name=name), patch.object(socket,name) as resolver:
    with network_guard():
     with self.assertRaises(UnexpectedNetworkAccess):getattr(socket,name)(*args)
    resolver.assert_not_called()
    self.assertIs(getattr(socket,name),resolver)

 def test_caught_network_attempt_cannot_produce_success(self):
  safe={"network_enabled":False,"orders_enabled":False,
        "model_inference_performed":False,"validated_for_trading":False}
  def swallowing_pipeline(*args):
   try:socket.create_connection(("127.0.0.1",80))
   except UnexpectedNetworkAccess:pass
   return safe
  with patch("offline_network_guard_v242.run_pipeline",side_effect=swallowing_pipeline):
   with self.assertRaisesRegex(UnexpectedNetworkAccess,"OFFLINE_PIPELINE_NETWORK_BLOCKED"):
    run_guarded_pipeline(source(),NOW)

 def test_exception_restores_all_guarded_functions(self):
  original=socket.getaddrinfo
  original_connect=socket.socket.connect
  with self.assertRaisesRegex(ValueError,"injected failure"):
   with network_guard():raise ValueError("injected failure")
  self.assertIs(socket.getaddrinfo,original)
  self.assertIs(socket.socket.connect,original_connect)

if __name__=="__main__":unittest.main()
