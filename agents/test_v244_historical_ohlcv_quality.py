import os
import csv
import json
import unittest
import subprocess
import sys
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
 def test_cli_output_symlink_does_not_overwrite_target(self):
  with TemporaryDirectory() as directory:
   source=Path(directory)/"history.csv"
   target=Path(directory)/"quality.json"
   unrelated=Path(directory)/"unrelated.json"
   unrelated.write_text("preserve me",encoding="utf-8")
   with source.open("w",newline="",encoding="utf-8") as handle:
    writer=csv.DictWriter(handle,fieldnames=("timestamp_ms","open","high","low","close","volume"))
    writer.writeheader()
    writer.writerows(candles())
   target.symlink_to(unrelated)
   with patch("sys.argv",["v244",str(source),str(target)]):
    main()
   self.assertEqual(unrelated.read_text(encoding="utf-8"),"preserve me")
   self.assertFalse(target.is_symlink())
   self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["quality_gate"],"PASS")
class CliRegressionTests(unittest.TestCase):
 def test_csv_parser_failure_removes_stale_report(self):
  with TemporaryDirectory() as directory:
   source=Path(directory)/"history.csv"
   target=Path(directory)/"quality.json"
   # csv.Error is distinct from ValueError: exercise the real parser limit.
   content="timestamp_ms,open,high,low,close,volume\n" + "1" * 100 + ",1,2,1,2,3\n"
   source.write_text(content,encoding="utf-8")
   target.write_text('{"quality_gate":"PASS"}',encoding="utf-8")
   previous=csv.field_size_limit(64)
   try:
    with patch("sys.argv",["v244",str(source),str(target)]):
     with self.assertRaises(csv.Error):
      main()
   finally:
    csv.field_size_limit(previous)
   self.assertEqual(source.read_text(encoding="utf-8"),content)
   self.assertFalse(target.exists())
   self.assertEqual(list(Path(directory).glob(".quality.json.*.tmp")),[])

 def write_history(self, source):
  with source.open("w", newline="", encoding="utf-8") as handle:
   writer=csv.DictWriter(handle,fieldnames=("timestamp_ms","open","high","low","close","volume"))
   writer.writeheader()
   writer.writerows(candles())

 def test_source_symlink_alias_is_rejected_before_cleanup(self):
  with TemporaryDirectory() as directory:
   source=Path(directory)/"history.csv"
   alias=Path(directory)/"quality.json"
   source.write_bytes(b"invalid CSV")
   alias.symlink_to(source)
   with patch("sys.argv",["v244",str(source),str(alias)]):
    with self.assertRaisesRegex(ValueError,"INPUT_OUTPUT_PATH_COLLISION"):
     main()
   self.assertEqual(source.read_bytes(),b"invalid CSV")
   self.assertTrue(alias.is_symlink())

 def test_replace_failure_cleans_temp_and_preserves_sources(self):
  for symlink in (False, True):
   with self.subTest(symlink=symlink), TemporaryDirectory() as directory:
    root=Path(directory)
    source=root/"history.csv"
    target=root/"quality.json"
    unrelated=root/"unrelated.json"
    self.write_history(source)
    original=source.read_bytes()
    unrelated.write_bytes(b"preserve me")
    if symlink:
     target.symlink_to(unrelated)
    else:
     target.write_text('{"quality_gate":"PASS"}',encoding="utf-8")
    def fail_replace(temporary, destination):
     self.assertEqual(Path(temporary).parent,root)
     self.assertEqual(Path(destination),target)
     self.assertEqual(json.loads(Path(temporary).read_text())["bars"],300)
     raise OSError("injected replace failure")
    with patch("sys.argv",["v244",str(source),str(target)]), patch("historical_ohlcv_quality_v244.os.replace",side_effect=fail_replace) as replace:
     with self.assertRaisesRegex(OSError,"injected replace failure"):
      main()
    replace.assert_called_once()
    self.assertEqual(source.read_bytes(),original)
    self.assertEqual(unrelated.read_bytes(),b"preserve me")
    self.assertFalse(target.exists())
    self.assertFalse(target.is_symlink())
    self.assertEqual(list(root.glob(".quality.json.*.tmp")),[])

 def test_csv_schema_and_row_width_fail_closed(self):
  header="timestamp_ms,open,high,low,close,volume"
  cases=[
   ("", "INVALID_CSV_SCHEMA"),
   (header+",extra\n1,1,2,1,2,3,x\n", "INVALID_CSV_SCHEMA"),
   ("timestamp_ms,open,high,low,close,close\n1,1,2,1,2,3\n", "INVALID_CSV_SCHEMA"),
   (header+"\n1,1,2,1,2\n", "INVALID_CSV_ROW"),
   (header+"\n1,1,2,1,2,3,extra\n", "INVALID_CSV_ROW"),
  ]
  for content,error in cases:
   with self.subTest(content=content), TemporaryDirectory() as directory:
    source=Path(directory)/"history.csv"
    target=Path(directory)/"quality.json"
    source.write_text(content,encoding="utf-8")
    target.write_text('{"quality_gate":"PASS"}',encoding="utf-8")
    with patch("sys.argv",["v244",str(source),str(target)]):
     with self.assertRaisesRegex(ValueError,error):
      main()
    self.assertEqual(source.read_text(encoding="utf-8"),content)
    self.assertFalse(target.exists())

 def test_cli_subprocess_success_and_conversion_failure(self):
  with TemporaryDirectory() as directory:
   source=Path(directory)/"history.csv"
   target=Path(directory)/"quality.json"
   self.write_history(source)
   command=[sys.executable,str(Path(__file__).with_name("historical_ohlcv_quality_v244.py")),str(source),str(target)]
   result=subprocess.run(command,capture_output=True,text=True,timeout=10)
   self.assertEqual(result.returncode,0,result.stderr)
   report=json.loads(target.read_text(encoding="utf-8"))
   self.assertEqual(report["bars"],300)
   self.assertEqual(report["quality_gate"],"PASS")
   self.assertFalse(report["orders_enabled"])
   self.assertFalse(report["backtest_performed"])
   for column,value in (("timestamp_ms","bad"),("open","bad"),("volume","nan")):
    with self.subTest(column=column,value=value):
     self.write_history(source)
     with source.open(encoding="utf-8",newline="") as handle:
      reader=csv.DictReader(handle)
      fields=reader.fieldnames
      rows=list(reader)
     rows[0][column]=value
     with source.open("w",encoding="utf-8",newline="") as handle:
      writer=csv.DictWriter(handle,fieldnames=fields)
      writer.writeheader();writer.writerows(rows)
     original=source.read_bytes()
     target.write_text('{"quality_gate":"PASS"}',encoding="utf-8")
     result=subprocess.run(command,capture_output=True,text=True,timeout=10)
     self.assertNotEqual(result.returncode,0)
     self.assertFalse(target.exists())
     self.assertEqual(source.read_bytes(),original)

if __name__=="__main__":unittest.main()
