import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from research_journal_v69 import append_run
from research_operator_v71 import snapshot

NOW = datetime(2026, 10, 24, 0, tzinfo=timezone.utc)
STAMP = NOW.isoformat()

def seed(root):
    for version, filename in (("v63", "diagnostics.json"), ("v64", "archive_lag.json"),
                              ("v65", "quality.json"), ("v66", "health.json")):
        path = root / version / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": version.upper()+".0", "generated_utc": STAMP,
                   "live_trading_approved": False}
        if version == "v66":
            payload["status"] = "RESEARCH_DATA_CHECKS_PASS"
        path.write_text(json.dumps(payload))
    from research_manifest_v68 import inspect_bundle
    manifest = root / "v68/manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(inspect_bundle(root)))
    append_run(root / "v69/runs.jsonl", manifest, root / "v66/health.json")

class OperatorTests(unittest.TestCase):
    def test_ready_only_for_consistent_recent_reports(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            seed(root)
            result = snapshot(root, NOW)
            self.assertEqual(result["status"], "OBSERVATION_READY")
            self.assertFalse(result["live_trading_approved"])

    def test_missing_journal_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            seed(root)
            (root / "v69/runs.jsonl").unlink()
            self.assertEqual(snapshot(root, NOW)["status"], "BLOCKED")

    def test_stale_health_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            seed(root)
            self.assertIn("HEALTH_REPORT_STALE_OR_FUTURE",
                          snapshot(root, datetime(2026, 10, 26, tzinfo=timezone.utc))["blockers"])

    def test_corrupt_report_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            seed(root)
            (root / "v65/quality.json").write_text("{")
            self.assertEqual(snapshot(root, NOW)["status"], "BLOCKED")

    def test_blocked_health_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            seed(root)
            p = root / "v66/health.json"
            obj = json.loads(p.read_text())
            obj["status"] = "BLOCKED"
            p.write_text(json.dumps(obj))
            self.assertIn("RESEARCH_HEALTH_BLOCKED", snapshot(root, NOW)["blockers"])

if __name__ == "__main__":
    unittest.main()
