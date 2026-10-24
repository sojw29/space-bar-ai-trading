import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from alerts_dashboard_v94 import dashboard_with_alerts

def source(d="LOCAL_STATUS_PASS", o="OPERATIONAL", streak=0):
    return {"status": d, "diagnostics": {"status": d},
            "operations": {"status": o, "consecutive_failures": streak}}

class AlertDashboardTests(unittest.TestCase):
    @patch("alerts_dashboard_v94.combined_status", return_value=source())
    def test_clear_local_status(self, _):
        result = dashboard_with_alerts()
        self.assertEqual(result["severity"], "INFO")
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["auto_remediation"])

    @patch("alerts_dashboard_v94.combined_status", return_value=source(d="BLOCKED"))
    def test_diagnostics_blocked(self, _):
        self.assertEqual(dashboard_with_alerts()["severity"], "CRITICAL")

    @patch("alerts_dashboard_v94.combined_status", return_value=source(o="REVIEW"))
    def test_missing_operations_warning(self, _):
        self.assertEqual(dashboard_with_alerts()["severity"], "WARNING")

    @patch("alerts_dashboard_v94.combined_status", return_value=source(streak=3))
    def test_repeated_failure_alert(self, _):
        result = dashboard_with_alerts()
        self.assertIn("REPEATED_FAILURES", [x["code"] for x in result["alerts"]])

    def test_real_missing_repo_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            result = dashboard_with_alerts(repo=Path(d))
            self.assertEqual(result["severity"], "CRITICAL")
            self.assertFalse(result["live_trading_approved"])

if __name__ == "__main__":
    unittest.main()
