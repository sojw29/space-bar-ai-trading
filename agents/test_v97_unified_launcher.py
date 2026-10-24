import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unified_launcher_v97 import execute

class UnifiedLauncherTests(unittest.TestCase):
    def test_unknown_action_rejected(self):
        with self.assertRaises(ValueError):
            execute("live-trade")

    @patch("unified_launcher_v97.assess", return_value={"status": "BLOCKED"})
    def test_readiness_dispatch(self, mock):
        result = execute("readiness")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["live_trading_approved"])
        mock.assert_called_once()

    @patch("unified_launcher_v97.dashboard_with_alerts", return_value={"severity": "WARNING"})
    def test_alerts_dispatch(self, _):
        self.assertEqual(execute("alerts")["status"], "WARNING")

    @patch("unified_launcher_v97.generate", return_value={"status": "REVIEW"})
    def test_report_dispatch(self, mock):
        with tempfile.TemporaryDirectory() as d:
            result = execute("report", repo=Path(d))
            self.assertEqual(result["status"], "REVIEW")
            self.assertEqual(mock.call_args.kwargs["output_dir"], Path(d).resolve() / "reports" / "v97")

    def test_real_empty_repo_readiness_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            result = execute("readiness", repo=Path(d))
            self.assertEqual(result["status"], "BLOCKED")

    def test_real_empty_repo_alerts_critical(self):
        with tempfile.TemporaryDirectory() as d:
            result = execute("alerts", repo=Path(d))
            self.assertEqual(result["status"], "CRITICAL")

if __name__ == "__main__":
    unittest.main()
