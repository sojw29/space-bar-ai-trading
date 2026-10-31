import unittest
from datetime import datetime, timezone, timedelta
from public_market_diagnostics_v224 import assess, SYMBOLS

NOW=datetime(2026,10,31,2,tzinfo=timezone.utc)
def sample():
    return {"version":"V223.0","research_only":True,"orders_enabled":False,
        "realtime":False,"agent_analysis_available":False,
        "captured_at_utc":NOW.isoformat(),
        "markets":[{"symbol":s,"last_price":100.0,"volume_24h":1234.0} for s in SYMBOLS]}

class DiagnosticTests(unittest.TestCase):
    def test_no_ai_or_orders(self):
        result=assess(sample(),now=NOW)
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["ai_agents_running"])
        self.assertFalse(result["trade_signals_available"])
        self.assertEqual(result["QUANT"]["status"],"INSUFFICIENT_HISTORY")
    def test_stale_fails_closed(self):
        with self.assertRaises(ValueError):
            assess(sample(),now=NOW+timedelta(hours=9))
    def test_duplicate_symbol_fails_closed(self):
        data=sample();data["markets"][1]["symbol"]="BTCUSDT"
        with self.assertRaises(ValueError):assess(data,now=NOW)
    def test_unsafe_snapshot_fails_closed(self):
        data=sample();data["orders_enabled"]=True
        with self.assertRaises(ValueError):assess(data,now=NOW)

if __name__=="__main__":unittest.main()
