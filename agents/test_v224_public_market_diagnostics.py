import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from public_market_diagnostics_v224 import assess, publish, SYMBOLS

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

    def test_invalid_input_removes_previous_public_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"market.json"
            destination=Path(directory)/"diagnostics.json"
            data=sample();data["orders_enabled"]=True
            source.write_text(json.dumps(data),encoding="utf-8")
            destination.write_text('{"version":"V224.0","stale":true}',encoding="utf-8")
            with self.assertRaises(ValueError):
                publish(source,destination,now=NOW)
            self.assertFalse(destination.exists())

    def test_missing_input_removes_previous_public_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"missing.json"
            destination=Path(directory)/"diagnostics.json"
            destination.write_text("old",encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                publish(source,destination,now=NOW)
            self.assertFalse(destination.exists())

    def test_same_source_destination_rejected_without_deleting_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"market.json"
            raw=json.dumps(sample())
            source.write_text(raw,encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"DIAGNOSTIC_SOURCE_DESTINATION_SAME"):
                publish(source,source,now=NOW)
            self.assertEqual(source.read_text(encoding="utf-8"),raw)

    def test_valid_input_publishes_read_only_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"market.json"
            destination=Path(directory)/"diagnostics.json"
            source.write_text(json.dumps(sample()),encoding="utf-8")
            publish(source,destination,now=NOW)
            output=json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(output["version"],"V224.0")
            self.assertFalse(output["orders_enabled"])
            self.assertFalse(output["ai_agents_running"])

if __name__=="__main__":unittest.main()
