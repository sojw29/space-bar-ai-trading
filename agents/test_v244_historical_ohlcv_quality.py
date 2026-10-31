import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from historical_ohlcv_quality_v244 import validate_candles, INTERVAL_MS, main
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
 def test_rejects_invalid_min_bars(self):
  with self.assertRaisesRegex(ValueError,"INVALID_MIN_BARS"):
   validate_candles(candles(),now=NOW,min_bars=0)
 def test_cli_never_deletes_source_when_input_equals_output(self):
  with TemporaryDirectory() as directory:
   source=Path(directory)/"history.csv"
   original="timestamp_ms,open,high,low,close,volume\nbad,1,2,1,2,3\n"
   source.write_text(original,encoding="utf-8")
   with patch("sys.argv",["v244",str(source),str(source)]):
    with self.assertRaisesRegex(ValueError,"INPUT_OUTPUT_PATH_COLLISION"):
     main()
   self.assertEqual(source.read_text(encoding="utf-8"),original)
 def test_cli_invalid_source_removes_stale_distinct_output(self):
  with TemporaryDirectory() as directory:
   source=Path(directory)/"history.csv"
   target=Path(directory)/"quality.json"
   source.write_text("timestamp_ms,open,high,low,close,volume\nbad,1,2,1,2,3\n",encoding="utf-8")
   target.write_text('{"quality_gate":"PASS"}',encoding="utf-8")
   with patch("sys.argv",["v244",str(source),str(target)]):
    with self.assertRaises(ValueError):
     main()
   self.assertTrue(source.exists())
   self.assertFalse(target.exists())
 def test_cli_never_deletes_source_hardlink_alias(self):
  with TemporaryDirectory() as directory:
   source=Path(directory)/"history.csv"
   alias=Path(directory)/"quality.json"
   source.write_text("invalid",encoding="utf-8")
   os.link(source,alias)
   with patch("sys.argv",["v244",str(source),str(alias)]):
    with self.assertRaisesRegex(ValueError,"INPUT_OUTPUT_PATH_COLLISION"):
     main()
   self.assertEqual(source.read_text(encoding="utf-8"),"invalid")
   self.assertEqual(alias.read_text(encoding="utf-8"),"invalid")
if __name__=="__main__":unittest.main()
