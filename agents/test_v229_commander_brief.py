import unittest
from datetime import datetime,timezone,timedelta
from commander_research_brief_v229 import summarize,SYMBOLS
NOW=datetime(2026,10,31,2,tzinfo=timezone.utc)
def sample():
 return {"version":"V228.0","analysis_type":"DETERMINISTIC_INDICATOR_DESCRIPTION",
 "research_only":True,"orders_enabled":False,"realtime":False,"ai_agents_running":False,
 "trade_signals_available":False,"source_generated_at_utc":NOW.isoformat(),
 "markets":[{"symbol":s,"ATLAS":{"sma_relationship":"SMA50_ABOVE_SMA200"},
 "QUANT":{"status":"DESCRIPTIVE_ONLY_NO_BACKTEST","volume_ratio_20":1.5},
 "GUARDIAN":{"status":"NO_TRADE_AUTHORIZATION","orders_enabled":False}} for s in SYMBOLS]}
class CommanderTests(unittest.TestCase):
 def test_compiles_without_ai_or_orders(self):
  report=summarize(sample(),NOW)
  self.assertEqual(len(report["markets"]),3)
  self.assertFalse(report["orders_enabled"])
  self.assertFalse(report["ai_agents_running"])
  self.assertFalse(report["backtest_verified"])
 def test_stale_rejected(self):
  with self.assertRaises(ValueError):summarize(sample(),NOW+timedelta(hours=9))
 def test_guardian_bypass_rejected(self):
  data=sample();data["markets"][0]["GUARDIAN"]["orders_enabled"]=True
  with self.assertRaises(ValueError):summarize(data,NOW)
 def test_duplicate_rejected(self):
  data=sample();data["markets"][1]["symbol"]="BTCUSDT"
  with self.assertRaises(ValueError):summarize(data,NOW)
if __name__=="__main__":unittest.main()
