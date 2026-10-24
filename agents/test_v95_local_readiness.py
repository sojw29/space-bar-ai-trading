import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from local_readiness_v95 import assess

def source(status="LOCAL_STATUS_PASS", severity="INFO", operations="OPERATIONAL", streak=0):
    return {"status": status, "severity": severity,
            "operations": {"status": operations, "consecutive_failures": streak}}

class LocalReadinessTests(unittest.TestCase):
    @patch("local_readiness_v95.dashboard_with_alerts", return_value=source())
    def test_local_ready_is_not_trading_approval(self, _):
        result = assess()
        self.assertEqual(result["status"], "LOCAL_REPORT_READY")
        self.assertFalse(result["live_trading_approved"])
        self.assertEqual(result["scope"], "LOCAL_REPORTING_ONLY")

    @patch("local_readiness_v95.dashboard_with_alerts", return_value=source(status="BLOCKED"))
    def test_diagnostics_blocked(self, _):
        self.assertEqual(assess()["status"], "BLOCKED")

    @patch("local_readiness_v95.dashboard_with_alerts", return_value=source(severity="CRITICAL"))
    def test_critical_alerts_blocked(self, _):
        self.assertEqual(assess()["status"], "BLOCKED")

    @patch("local_readiness_v95.dashboard_with_alerts", return_value=source(operations="REVIEW"))
    def test_missing_journal_blocked(self, _):
        self.assertEqual(assess()["status"], "BLOCKED")

    @patch("local_readiness_v95.dashboard_with_alerts", return_value=source(streak=2))
    def test_recent_failures_blocked(self, _):
        self.assertEqual(assess()["status"], "BLOCKED")

    @patch("local_readiness_v95.dashboard_with_alerts", return_value=source())
    @patch("local_readiness_v95.render", side_effect=ValueError("broken"))
    def test_broken_html_renderer_blocks(self, *_):
        self.assertEqual(assess()["status"], "BLOCKED")

    def test_real_empty_repo_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            result = assess(repo=Path(d))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["total"], 5)

if __name__ == "__main__":
    unittest.main()
