import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from local_status_v72 import render, run

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)

class StatusCliTests(unittest.TestCase):
    def test_missing_reports_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            result = run(Path(d), NOW)
            self.assertEqual(result["research_status"]["status"], "BLOCKED")
            self.assertFalse(result["live_trading_approved"])

    def test_human_readable_output(self):
        status = {"status": "BLOCKED", "journal_valid_entries": 2,
                  "blockers": ["JOURNAL_INVALID_OR_MISSING"], "warnings": []}
        text = render(status)
        self.assertIn("BLOCKED", text)
        self.assertIn("Live trading: DISABLED", text)
        self.assertIn("JOURNAL_INVALID_OR_MISSING", text)

    def test_review_display(self):
        status = {"status": "REVIEW", "journal_valid_entries": 5,
                  "blockers": [], "warnings": ["RESEARCH_HEALTH_REVIEW"]}
        self.assertIn("MANUAL REVIEW NEEDED", render(status))

    def test_ready_display_is_not_live_approval(self):
        status = {"status": "OBSERVATION_READY", "journal_valid_entries": 1,
                  "blockers": [], "warnings": []}
        output = render(status)
        self.assertIn("RESEARCH OBSERVATION READY", output)
        self.assertIn("Live trading: DISABLED", output)

    def test_json_serializable(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(json.loads(json.dumps(run(Path(d), NOW)))["version"], "V72.0")

if __name__ == "__main__":
    unittest.main()
