import unittest
from unittest.mock import patch
from desktop_gui_v83 import ACTIONS, run_action

class DesktopGuiTests(unittest.TestCase):
    def test_allowed_actions_exact(self):
        self.assertEqual({a for _, a in ACTIONS}, {"pc-check", "audit", "self-test"})

    def test_disallowed_action(self):
        with self.assertRaisesRegex(ValueError, "ACTION_NOT_ALLOWED"):
            run_action("trade")

    @patch("desktop_gui_v83.launch", return_value={"status": "REVIEW"})
    def test_pc_dispatch(self, launcher):
        result = run_action("pc-check")
        launcher.assert_called_once_with("pc-check", repo=None)
        self.assertEqual(result["status"], "REVIEW")
        self.assertFalse(result["live_trading_approved"])

    @patch("desktop_gui_v83.launch", return_value={"status": "BLOCKED"})
    def test_audit_dispatch(self, launcher):
        self.assertEqual(run_action("audit")["status"], "BLOCKED")
        launcher.assert_called_once_with("audit", repo=None)

    @patch("desktop_gui_v83.launch", return_value={"status": "PASS"})
    def test_self_test_dispatch(self, launcher):
        self.assertEqual(run_action("self-test")["status"], "PASS")

    def test_real_self_test_without_gui(self):
        result = run_action("self-test")
        self.assertEqual(result["status"], "PASS", result)

if __name__ == "__main__":
    unittest.main()
