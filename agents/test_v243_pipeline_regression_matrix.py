import unittest
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from pipeline_regression_matrix_v243 import evaluate_matrix, main
from offline_network_guard_v242 import UnexpectedNetworkAccess
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
class MatrixTests(unittest.TestCase):
 def test_nine_unsafe_mutations_are_rejected(self):
  result=evaluate_matrix(source(),NOW)
  self.assertEqual(result["rejected_count"],9)
  self.assertTrue(all(row["status"]=="REJECTED_AS_EXPECTED" for row in result["scenarios"]))
  self.assertFalse(result["orders_enabled"])
  self.assertFalse(result["network_enabled"])
 def test_deterministic_result(self):
  self.assertEqual(evaluate_matrix(source(),NOW),evaluate_matrix(source(),NOW))
 def test_invalid_baseline_is_not_reported_as_success(self):
  data=source();data["orders_enabled"]=True
  with self.assertRaises(ValueError):evaluate_matrix(data,NOW)
 def test_source_is_not_mutated(self):
  data=source();before=data["markets"][0]["volume_ratio_20"]
  evaluate_matrix(data,NOW)
  self.assertEqual(data["markets"][0]["volume_ratio_20"],before)
class CliFileSafetyTests(unittest.TestCase):
 def test_input_aliases_preserve_source(self):
  for kind in ("same", "hardlink", "symlink"):
   with self.subTest(kind=kind), TemporaryDirectory() as directory:
    original=Path(directory)/"source.json"
    original.write_bytes(b"invalid JSON")
    target=original if kind=="same" else Path(directory)/"report.json"
    if kind=="hardlink":os.link(original,target)
    if kind=="symlink":target.symlink_to(original)
    with patch("sys.argv",["v243",str(original),str(target)]):
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
    expected=evaluate_matrix(source(),NOW)
    real_replace=os.replace
    def replace(temporary,destination):
     self.assertEqual(Path(temporary).parent,root)
     self.assertEqual(json.loads(Path(temporary).read_text(encoding="utf-8")),expected)
     if fail:raise OSError("injected replace failure")
     real_replace(temporary,destination)
    with patch("sys.argv",["v243",str(original),str(target)]), patch("pipeline_regression_matrix_v243.evaluate_matrix",return_value=expected), patch("pipeline_regression_matrix_v243.os.replace",side_effect=replace):
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
   with patch("sys.argv",["v243",str(original),str(target)]):
    with self.assertRaises(ValueError):main()
   self.assertEqual(original.read_bytes(),b"invalid JSON")
   self.assertFalse(target.exists())

 def test_pipeline_rejection_and_serialization_failure_cleanup(self):
  for failure in ("pipeline", "serialization", "network"):
   with self.subTest(failure=failure), TemporaryDirectory() as directory:
    root=Path(directory)
    original=root/"source.json"
    original.write_text(json.dumps(source()),encoding="utf-8")
    before=original.read_bytes()
    target=root/"report.json"
    target.write_text('{"baseline":"PASS"}',encoding="utf-8")
    options={"return_value":{"invalid":float("nan")}}
    if failure=="pipeline":options={"side_effect":AssertionError("UNSAFE_SCENARIO_ACCEPTED:test")}
    if failure=="network":options={"side_effect":UnexpectedNetworkAccess("OFFLINE_PIPELINE_NETWORK_BLOCKED")}
    with patch("sys.argv",["v243",str(original),str(target)]), patch("pipeline_regression_matrix_v243.evaluate_matrix",**options):
     with self.assertRaises((AssertionError,ValueError,UnexpectedNetworkAccess)):main()
    self.assertEqual(original.read_bytes(),before)
    self.assertFalse(target.exists())
    self.assertEqual(list(root.glob(".report.json.*.tmp")),[])

if __name__=="__main__":unittest.main()
