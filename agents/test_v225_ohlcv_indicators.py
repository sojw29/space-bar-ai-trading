import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from ohlcv_indicators_v225 import indicators, build, SYMBOLS

class IndicatorsTests(unittest.TestCase):
    def fake(self,symbol):
        now=int(datetime.now(timezone.utc).timestamp()//300)*300000
        bars=[]
        for i in range(210):
            ts=now-(210-i)*300000
            price=100+i*0.1
            bars.append([str(ts),str(price),str(price+1),str(price-1),str(price),"50","0"])
        return {"retCode":0,"result":{"list":list(reversed(bars))}}
    def test_completed_candle_indicators(self):
        with patch("ohlcv_indicators_v225.datetime") as dt:
            dt.now.return_value=datetime.now(timezone.utc)
            dt.fromtimestamp.side_effect=datetime.fromtimestamp
            m=indicators("BTCUSDT",self.fake)
        self.assertGreater(m["sma50"],m["sma200"])
        self.assertEqual(m["trend_label"],"SMA50_ABOVE_SMA200")
    def test_reject_gaps(self):
        def gap(symbol):
            data=self.fake(symbol);data["result"]["list"].pop(5);return data
        with self.assertRaises(ValueError):indicators("BTCUSDT",gap)
    def test_research_only(self):
        result=build(self.fake)
        self.assertEqual(len(result["markets"]),len(SYMBOLS))
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["trade_signals_available"])
if __name__=="__main__":unittest.main()
