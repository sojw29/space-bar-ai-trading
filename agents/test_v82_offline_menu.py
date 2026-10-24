import unittest
from unittest.mock import patch
from offline_menu_v82 import choose, run_menu

class OfflineMenuTests(unittest.TestCase):
    def test_exit(self):
        self.assertEqual(choose("0")["status"], "EXIT")

    def test_invalid_selection(self):
        self.assertEqual(choose("live")["status"], "INVALID_SELECTION")

    @patch("offline_menu_v82.launch", return_value={"status": "PASS"})
    def test_self_test_dispatch(self, launcher):
        result = choose("3")
        launcher.assert_called_once_with("self-test", repo=None, reports=None, log=None)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["live_trading_approved"])

    @patch("offline_menu_v82.launch", return_value={"status": "BLOCKED"})
    def test_pc_check_dispatch(self, launcher):
        self.assertEqual(choose("1")["status"], "BLOCKED")
        launcher.assert_called_once_with("pc-check", repo=None, reports=None, log=None)

    @patch("offline_menu_v82.launch", return_value={"status": "REVIEW"})
    def test_audit_dispatch(self, launcher):
        self.assertEqual(choose("2", log="history.jsonl")["status"], "REVIEW")
        launcher.assert_called_once_with("audit", repo=None, reports=None, log="history.jsonl")

    def test_menu_exit_input(self):
        output = []
        result = run_menu(input_fn=lambda _: "0", output_fn=output.append)
        self.assertEqual(result, 0)
        self.assertTrue(any("closed" in x for x in output))

    def test_menu_invalid_then_exit(self):
        selections = iter(["9", "0"])
        output = []
        run_menu(input_fn=lambda _: next(selections), output_fn=output.append)
        self.assertTrue(any("Invalid selection" in x for x in output))

    def test_real_integration_self_test(self):
        self.assertEqual(choose("3")["status"], "PASS")

if __name__ == "__main__":
    unittest.main()
