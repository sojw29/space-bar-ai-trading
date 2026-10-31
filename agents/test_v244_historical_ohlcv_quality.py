import unittest
from datetime import datetime, timezone, timedelta
from historical_ohlcv_quality_v244 import validate_candles, INTERVAL_MS
NOW=datetime(2026,10,31,6,tzinfo=timezone.utc)
def candles():
 end=int((NOW-timedelta(minutes=5)).timestamp()*1000)
 end-=end%INTERVAL_MS
 return [{"timestamp_ms":end-(299-i)*INTERVAL_MS,
 "open":100.0,"high":102.0,"low":99.0,"close":101.0,"volume":200.0}
 for i in range(300)]
class QualityTests(unittest.TestCase):
 def test_valid_history(self):
  result=validate_candles(candles(),now=NOW)
  self.assertEqual(result["bars"],300)
  self.assertEqual(result["quality_gate"],"PASS")
  self.assertFalse(result["backtest_performed"])
 def test_rejects_gap(self):
  data=candles();data[20]["timestamp_ms"]+=INTERVAL_MS
  with self.assertRaises(ValueError):validate_candles(data,now=NOW)
 def test_rejects_duplicate(self):
  data=candles();data[20]["timestamp_ms"]=data[19]["timestamp_ms"]
  with self.assertRaises(ValueError):validate_candles(data,now=NOW)
 def test_rejects_bad_ohlc(self):
  data=candles();data[0]["high"]=98.0
  with self.assertRaises(ValueError):validate_candles(data,now=NOW)
 def test_rejects_nonfinite(self):
  data=candles();data[0]["volume"]=float("nan")
  with self.assertRaises(ValueError):validate_candles(data,now=NOW)
 def test_rejects_incomplete_last_candle(self):
  data=candles();data[-1]["timestamp_ms"]=int(NOW.timestamp()*1000)
  with self.assertRaises(ValueError):validate_candles(data,now=NOW)
 def test_rejects_insufficient_history(self):
  with self.assertRaises(ValueError):validate_candles(candles()[:299],now=NOW)
if __name__=="__main__":unittest.main()
