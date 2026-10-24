import unittest
from integration_verifier_v98 import verify

class OfflineIntegrationTests(unittest.TestCase):
    def test_complete_isolated_pipeline(self):
        result = verify()
        self.assertEqual(result["status"], "INTEGRATION_PASS", result)
        self.assertEqual(result["passed"], result["total"])
        self.assertGreaterEqual(result["total"], 8)
        self.assertFalse(result["live_trading_approved"])
        self.assertEqual(result["scope"], "OFFLINE_LOCAL_REPORTING_ONLY")

    def test_failure_fixture_and_sanitized_report(self):
        result = verify()
        codes = {check["name"]: check["status"] for check in result["checks"]}
        for code in ("READINESS_FAIL_CLOSED", "ALERTS_FAIL_CLOSED",
                     "REPORT_FILES_CREATED", "REPORT_SANITIZED",
                     "REPORT_STATUS_NOT_PROMOTED", "FAILED_OPERATION_BLOCKS",
                     "NO_AUTOMATED_ORDERS"):
            self.assertEqual(codes[code], "PASS", code)

if __name__ == "__main__":
    unittest.main()
