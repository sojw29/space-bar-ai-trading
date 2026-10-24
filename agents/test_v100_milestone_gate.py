import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from milestone_gate_v100 import milestone

class MilestoneGateTests(unittest.TestCase):
    def test_real_offline_milestone(self):
        result = milestone()
        self.assertEqual(result["status"], "OFFLINE_MILESTONE_PASS", result)
        self.assertEqual(result["passed"], 3)
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["real_orders_enabled"])
        self.assertIn("strategy profitability", result["not_validated"])

    def test_missing_repository_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            result = milestone(Path(d))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["checks"][0]["status"], "BLOCKED")

    @patch("milestone_gate_v100.verify", return_value={"status": "INTEGRATION_FAIL", "live_trading_approved": False})
    def test_failed_integration_blocks(self, _):
        self.assertEqual(milestone()["status"], "BLOCKED")

    @patch("milestone_gate_v100.preflight", return_value={"status": "ENVIRONMENT_PASS", "live_trading_approved": True})
    def test_unsafe_environment_blocks(self, _):
        result = milestone()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["checks"][2]["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
