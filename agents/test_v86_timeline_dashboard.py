import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from timeline_dashboard_v86 import dashboard_data

class V86DashboardTests(unittest.TestCase):
    @patch("timeline_dashboard_v86.timeline", return_value={"status": "ANALYZED", "events": [], "transitions": [], "issues": []})
    @patch("timeline_dashboard_v86.build_snapshot", return_value={"status": "LOCAL_STATUS_PASS"})
    def test_all_pass(self, *_):
        result = dashboard_data()
        self.assertEqual(result["status"], "LOCAL_STATUS_PASS")
        self.assertFalse(result["live_trading_approved"])

    @patch("timeline_dashboard_v86.timeline", return_value={"status": "REVIEW", "events": [], "transitions": [], "issues": ["LOG_EMPTY"]})
    @patch("timeline_dashboard_v86.build_snapshot", return_value={"status": "LOCAL_STATUS_PASS"})
    def test_missing_history_requires_review(self, *_):
        self.assertEqual(dashboard_data()["status"], "REVIEW")

    @patch("timeline_dashboard_v86.timeline", return_value={"status": "REVIEW", "events": [], "transitions": [], "issues": []})
    @patch("timeline_dashboard_v86.build_snapshot", return_value={"status": "BLOCKED"})
    def test_blocked_precedence(self, *_):
        self.assertEqual(dashboard_data()["status"], "BLOCKED")

    @patch("timeline_dashboard_v86.timeline", return_value={"status": "ANALYZED", "events": [], "transitions": [], "issues": []})
    @patch("timeline_dashboard_v86.build_snapshot", return_value={"status": "REVIEW"})
    def test_current_review(self, *_):
        self.assertEqual(dashboard_data()["status"], "REVIEW")

    def test_real_empty_repo_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            result = dashboard_data(repo=Path(d))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["timeline"]["status"], "REVIEW")

if __name__ == "__main__":
    unittest.main()
