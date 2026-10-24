import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from desktop_status_v84 import build_snapshot

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)

class DashboardTests(unittest.TestCase):
    @patch("desktop_status_v84.analyze", return_value={"status": "ANALYZED"})
    @patch("desktop_status_v84.launch", side_effect=[{"status": "LOCAL_DIAGNOSTICS_PASS"}, {"status": "LOCAL_AUDIT_PASS"}])
    def test_ready_snapshot(self, launcher, trends):
        result = build_snapshot(now=NOW)
        self.assertEqual(result["status"], "LOCAL_STATUS_PASS")
        self.assertFalse(result["live_trading_approved"])
        self.assertEqual(launcher.call_count, 2)

    @patch("desktop_status_v84.analyze", return_value={"status": "INSUFFICIENT_DATA"})
    @patch("desktop_status_v84.launch", side_effect=[{"status": "REVIEW"}, {"status": "REVIEW"}])
    def test_review_snapshot(self, *_):
        self.assertEqual(build_snapshot(now=NOW)["status"], "REVIEW")

    @patch("desktop_status_v84.analyze", return_value={"status": "ANALYZED"})
    @patch("desktop_status_v84.launch", side_effect=[{"status": "BLOCKED"}, {"status": "REVIEW"}])
    def test_blocked_snapshot(self, *_):
        self.assertEqual(build_snapshot(now=NOW)["status"], "BLOCKED")

    def test_real_missing_repo_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            result = build_snapshot(repo=Path(d), now=NOW)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["live_trading_approved"])

    def test_deterministic_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            result = build_snapshot(repo=Path(d), now=NOW)
            self.assertEqual(result["timestamp_utc"], NOW.isoformat())

if __name__ == "__main__":
    unittest.main()
