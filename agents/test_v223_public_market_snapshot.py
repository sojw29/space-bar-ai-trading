import json
import tempfile
import unittest
from pathlib import Path
from public_market_snapshot_v223 import build, publish, SYMBOLS

class PublicMarketTests(unittest.TestCase):
    def test_valid_public_snapshot(self):
        def fake(symbol):
            return {"retCode":0,"result":{"list":[{"symbol":symbol,"lastPrice":"120.5","volume24h":"3400"}]}}
        result=build(fake)
        self.assertEqual([x["symbol"] for x in result["markets"]],list(SYMBOLS))
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["realtime"])
        self.assertFalse(result["agent_analysis_available"])

    def test_bad_symbol_rejected(self):
        with self.assertRaises(ValueError):
            build(lambda symbol: {"retCode":0,"result":{"list":[{"symbol":"OTHER","lastPrice":"1","volume24h":"2"}]}})

    def test_bad_price_rejected(self):
        with self.assertRaises(ValueError):
            build(lambda symbol: {"retCode":0,"result":{"list":[{"symbol":symbol,"lastPrice":"-1","volume24h":"2"}]}})

    def test_failed_feed_removes_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "market_snapshot.json"
            target.write_text('{"stale": true}', encoding="utf-8")
            def unavailable(symbol):
                raise OSError("HTTP 403")
            with self.assertRaises(OSError):
                publish(target, unavailable)
            self.assertFalse(target.exists())

    def test_success_replaces_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "market_snapshot.json"
            target.write_text('{"stale": true}', encoding="utf-8")
            def fake(symbol):
                return {"retCode": 0, "result": {"list": [
                    {"symbol": symbol, "lastPrice": "120.5", "volume24h": "3400"}
                ]}}
            publish(target, fake)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(len(data["markets"]), 3)
            self.assertFalse(data["orders_enabled"])
            self.assertNotIn("stale", data)

    def test_reject_nonfinite_market_price(self):
        def fake(symbol):
            return {"retCode": 0, "result": {"list": [
                {"symbol": symbol, "lastPrice": "NaN", "volume24h": "3400"}
            ]}}
        with self.assertRaises(ValueError):
            build(fake)

if __name__=="__main__":unittest.main()
