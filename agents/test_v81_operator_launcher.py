import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from operator_launcher_v81 import launch

class OperatorLauncherTests(unittest.TestCase):
    def test_disallowed_action(self):
        with self.assertRaisesRegex(ValueError, "ACTION_NOT_ALLOWED"):
            launch("live-trade")

    @patch("operator_launcher_v81.verify", return_value={"status": "PASS"})
    def test_self_test_dispatch(self, verify):
        result = launch("self-test")
        verify.assert_called_once_with()
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["live_trading_approved"])

    @patch("operator_launcher_v81.checklist", return_value={"status": "REVIEW"})
    def test_pc_check_dispatch(self, checklist):
        with tempfile.TemporaryDirectory() as d:
            result = launch("pc-check", repo=Path(d))
            self.assertEqual(result["status"], "REVIEW")
            checklist.assert_called_once()

    @patch("operator_launcher_v81.audit", return_value={"status": "BLOCKED"})
    def test_audit_dispatch(self, audit):
        with tempfile.TemporaryDirectory() as d:
            result = launch("audit", repo=Path(d))
            self.assertEqual(result["status"], "BLOCKED")
            audit.assert_called_once()

    def test_real_self_test_integration(self):
        result = launch("self-test")
        self.assertEqual(result["status"], "PASS", result)

    def test_empty_repo_stays_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            result = launch("pc-check", repo=Path(d))
            self.assertEqual(result["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
