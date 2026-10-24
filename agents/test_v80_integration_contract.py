import unittest
from unittest.mock import patch
from integration_contract_v80 import verify

class V80IntegrationTests(unittest.TestCase):
    def test_full_offline_contract(self):
        result = verify()
        self.assertEqual(result["status"], "PASS", result)
        self.assertTrue(all(result["checks"].values()))

    def test_no_live_trading(self):
        result = verify()
        self.assertFalse(result["live_trading_approved"])
        self.assertTrue(result["research_only"])

    def test_contract_catches_regression(self):
        with patch("integration_contract_v80.analyze", return_value={"status": "INSUFFICIENT_DATA", "total_runs": 0, "live_trading_approved": False}):
            result = verify()
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["checks"]["history_two_events"])

if __name__ == "__main__":
    unittest.main()
