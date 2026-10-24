import json
import tempfile
import unittest
from pathlib import Path
from research_manifest_v68 import inspect_bundle

VERSIONS = (("v63", "diagnostics.json"), ("v64", "archive_lag.json"),
            ("v65", "quality.json"), ("v66", "health.json"))
STAMP = "2026-10-24T00:00:00+00:00"

def seed(root):
    for version, filename in VERSIONS:
        path = root / version / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": version.upper()+".0",
                                    "generated_utc": STAMP,
                                    "live_trading_approved": False}))

class ManifestTests(unittest.TestCase):
    def test_consistent_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            seed(root)
            result = inspect_bundle(root)
            self.assertEqual(result["status"], "CONSISTENT_BUNDLE")
            self.assertEqual(len(result["reports"]), 4)
            self.assertEqual(len(result["reports"]["v63"]["sha256"]), 64)

    def test_missing_report_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            seed(root)
            (root / "v64/archive_lag.json").unlink()
            self.assertEqual(inspect_bundle(root)["status"], "BLOCKED")

    def test_mixed_generation_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            seed(root)
            p = root / "v65/quality.json"
            obj = json.loads(p.read_text())
            obj["generated_utc"] = "2026-10-23T00:00:00+00:00"
            p.write_text(json.dumps(obj))
            self.assertIn("MIXED_REPORT_GENERATION_TIMES", inspect_bundle(root)["issues"])

    def test_live_approval_not_false_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            seed(root)
            p = root / "v66/health.json"
            obj = json.loads(p.read_text())
            obj["live_trading_approved"] = True
            p.write_text(json.dumps(obj))
            self.assertEqual(inspect_bundle(root)["status"], "BLOCKED")

    def test_corrupted_json_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            seed(root)
            (root / "v63/diagnostics.json").write_text("{broken")
            self.assertEqual(inspect_bundle(root)["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
