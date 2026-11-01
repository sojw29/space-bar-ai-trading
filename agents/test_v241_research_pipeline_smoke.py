import unittest
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from research_pipeline_smoke_v241 import run_pipeline, main
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
class PipelineTests(unittest.TestCase):
 def test_full_pipeline_is_offline_and_no_trade(self):
  result=run_pipeline(source(),NOW)
  self.assertEqual(len(result["steps"]),6)
  self.assertEqual(result["steps"][1]["event_count"],12)
  self.assertFalse(result["orders_enabled"])
  self.assertFalse(result["network_enabled"])
  self.assertFalse(result["model_inference_performed"])
  self.assertFalse(result["validated_for_trading"])
 def test_deterministic_pipeline(self):
  self.assertEqual(run_pipeline(source(),NOW),run_pipeline(source(),NOW))
 def test_unsafe_source_fails_closed(self):
  data=source();data["orders_enabled"]=True
  with self.assertRaises(ValueError):run_pipeline(data,NOW)
 def test_stale_source_fails_closed(self):
  data=source();data["source_generated_at_utc"]=(NOW-timedelta(hours=9)).isoformat()
  with self.assertRaises(ValueError):run_pipeline(data,NOW)
 def test_missing_market_fails_closed(self):
  data=source();data["markets"].pop()
  with self.assertRaises(ValueError):run_pipeline(data,NOW)
class CliFileSafetyTests(unittest.TestCase):
 def test_input_aliases_preserve_source(self):
  for kind in ("same", "hardlink", "symlink"):
   with self.subTest(kind=kind), TemporaryDirectory() as directory:
    original=Path(directory)/"source.json"
    original.write_bytes(b"invalid JSON")
    target=original if kind=="same" else Path(directory)/"report.json"
    if kind=="hardlink":os.link(original,target)
    if kind=="symlink":target.symlink_to(original)
    with patch("sys.argv",["v241",str(original),str(target)]):
     with self.assertRaisesRegex(ValueError,"INPUT_OUTPUT_PATH_COLLISION"):
      main()
    self.assertEqual(original.read_bytes(),b"invalid JSON")
    self.assertEqual(target.read_bytes(),b"invalid JSON")

 def test_atomic_output_and_replace_failure(self):
  for fail in (False,True):
   with self.subTest(fail=fail), TemporaryDirectory() as directory:
    root=Path(directory)
    original=root/"source.json"
    original.write_text(json.dumps(source()),encoding="utf-8")
    target=root/"report.json"
    unrelated=root/"unrelated.json"
    unrelated.write_bytes(b"preserve me")
    target.symlink_to(unrelated)
    expected=run_pipeline(source(),NOW)
    real_replace=os.replace
    def replace(temporary,destination):
     self.assertEqual(Path(temporary).parent,root)
     self.assertEqual(json.loads(Path(temporary).read_text(encoding="utf-8")),expected)
     if fail:raise OSError("injected replace failure")
     real_replace(temporary,destination)
    with patch("sys.argv",["v241",str(original),str(target)]), patch("research_pipeline_smoke_v241.run_pipeline",return_value=expected), patch("research_pipeline_smoke_v241.os.replace",side_effect=replace):
     if fail:
      with self.assertRaisesRegex(OSError,"injected replace failure"):main()
     else:main()
    self.assertEqual(unrelated.read_bytes(),b"preserve me")
    self.assertEqual(json.loads(original.read_text()),source())
    self.assertFalse(target.is_symlink())
    if fail:self.assertFalse(target.exists())
    else:self.assertEqual(json.loads(target.read_text()),expected)
    self.assertEqual(list(root.glob(".report.json.*.tmp")),[])

 def test_invalid_input_removes_stale_report(self):
  with TemporaryDirectory() as directory:
   original=Path(directory)/"source.json"
   target=Path(directory)/"report.json"
   original.write_bytes(b"invalid JSON")
   target.write_text('{"baseline":"PASS"}',encoding="utf-8")
   with patch("sys.argv",["v241",str(original),str(target)]):
    with self.assertRaises(ValueError):main()
   self.assertEqual(original.read_bytes(),b"invalid JSON")
   self.assertFalse(target.exists())

if __name__=="__main__":unittest.main()
