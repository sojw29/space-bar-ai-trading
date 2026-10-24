import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from operation_journal_v90 import record_event, recent_events, run_logged

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)

def event(result="SUCCESS", status="REVIEW"):
    return {"version": "V90.0", "timestamp_utc": NOW.isoformat(),
            "operation": "MOBILE_REPORT", "result": result, "status": status,
            "research_only": True, "live_trading_approved": False}

class OperationJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "journal.jsonl"

    def test_record_and_read(self):
        record_event(self.path, event())
        self.assertEqual(recent_events(self.path)[0]["result"], "SUCCESS")

    def test_blocked_result(self):
        with patch("operation_journal_v90.generate", return_value={"status": "BLOCKED"}):
            output = run_logged(journal=self.path, now=NOW)
        self.assertEqual(output["result"], "BLOCKED")

    def test_exception_sanitized(self):
        with patch("operation_journal_v90.generate", side_effect=RuntimeError("SECRET_KEY=123")):
            output = run_logged(journal=self.path, now=NOW)
        self.assertEqual(output["result"], "FAILED")
        self.assertNotIn("SECRET_KEY", self.path.read_text(encoding="utf-8"))

    def test_unsafe_event_rejected(self):
        bad = event()
        bad["live_trading_approved"] = True
        with self.assertRaises(ValueError):
            record_event(self.path, bad)

    def test_bounded_history(self):
        for _ in range(105):
            record_event(self.path, event())
        self.assertEqual(len(recent_events(self.path, limit=100)), 100)

    def test_missing_history(self):
        self.assertEqual(recent_events(self.path), [])

    def test_real_pipeline_with_empty_repo(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "empty"
            repo.mkdir()
            output = run_logged(repo=repo, output_dir=Path(d) / "out",
                                journal=self.path, now=NOW)
            self.assertEqual(output["result"], "BLOCKED")
            self.assertFalse(output["live_trading_approved"])

if __name__ == "__main__":
    unittest.main()
