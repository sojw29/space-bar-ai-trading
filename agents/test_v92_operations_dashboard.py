import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from operations_dashboard_v92 import combined_status

class OperationsDashboardTests(unittest.TestCase):
    @patch("operations_dashboard_v92.summarize", return_value={"status": "OPERATIONAL", "consecutive_failures": 0})
    @patch("operations_dashboard_v92.dashboard_data", return_value={"status": "LOCAL_STATUS_PASS"})
    def test_all_good(self, *_):
        result = combined_status()
        self.assertEqual(result["status"], "LOCAL_STATUS_PASS")
        self.assertFalse(result["live_trading_approved"])

    @patch("operations_dashboard_v92.summarize", return_value={"status": "BLOCKED", "consecutive_failures": 2})
    @patch("operations_dashboard_v92.dashboard_data", return_value={"status": "LOCAL_STATUS_PASS"})
    def test_operation_failure_blocks(self, *_):
        self.assertEqual(combined_status()["status"], "BLOCKED")

    @patch("operations_dashboard_v92.summarize", return_value={"status": "REVIEW", "consecutive_failures": 0})
    @patch("operations_dashboard_v92.dashboard_data", return_value={"status": "LOCAL_STATUS_PASS"})
    def test_missing_operation_history_review(self, *_):
        self.assertEqual(combined_status()["status"], "REVIEW")

    @patch("operations_dashboard_v92.summarize", return_value={"status": "OPERATIONAL", "consecutive_failures": 0})
    @patch("operations_dashboard_v92.dashboard_data", return_value={"status": "BLOCKED"})
    def test_diagnostics_blocked_precedence(self, *_):
        self.assertEqual(combined_status()["status"], "BLOCKED")

    def test_real_empty_repo_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            result = combined_status(repo=Path(d))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["operations"]["status"], "REVIEW")

if __name__ == "__main__":
    unittest.main()
