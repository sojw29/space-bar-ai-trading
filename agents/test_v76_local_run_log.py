import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from local_run_log_v76 import record_run

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)

def result(status="BLOCKED"):
    return {"status": status, "environment": {"status": "REVIEW"},
            "research": {"status": "BLOCKED"}, "blockers": ["RESEARCH_BLOCKED"],
            "warnings": ["ENVIRONMENT_REVIEW"],
            "secret": "NEVER_STORE_ME", "private_path": "NEVER_STORE_ME"}

class LocalLogTests(unittest.TestCase):
    @patch("local_run_log_v76.diagnose", return_value=result())
    def test_log_redacts_unapproved_fields(self, _):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "events.jsonl"
            event = record_run(Path(d), path, now=NOW)
            text = path.read_text()
            self.assertNotIn("NEVER_STORE_ME", text)
            self.assertFalse(event["live_trading_approved"])

    @patch("local_run_log_v76.diagnose", return_value=result())
    def test_multiple_events_append(self, _):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "events.jsonl"
            record_run(Path(d), path, now=NOW)
            record_run(Path(d), path, now=NOW)
            self.assertEqual(len(path.read_text().splitlines()), 2)

    @patch("local_run_log_v76.diagnose", return_value=result())
    def test_incomplete_log_not_overwritten(self, _):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "events.jsonl"
            path.write_text('{"broken":')
            with self.assertRaisesRegex(ValueError, "EXISTING_LOG_INCOMPLETE"):
                record_run(Path(d), path, now=NOW)
            self.assertEqual(path.read_text(), '{"broken":')

    @patch("local_run_log_v76.diagnose", return_value=result("UNKNOWN"))
    def test_unknown_status_rejected(self, _):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "UNKNOWN_DIAGNOSTIC_STATUS"):
                record_run(Path(d), Path(d) / "events.jsonl", now=NOW)

    def test_missing_reports_still_logged_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            event = record_run(root, root / "events.jsonl", now=NOW)
            self.assertEqual(event["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
