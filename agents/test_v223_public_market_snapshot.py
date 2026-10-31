import unittest
from public_market_snapshot_v223 import build, SYMBOLS

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

if __name__=="__main__":unittest.main()
