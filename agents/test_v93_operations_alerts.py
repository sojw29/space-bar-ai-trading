import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from operations_alerts_v93 import evaluate, inspect

def data(d="LOCAL_STATUS_PASS", o="OPERATIONAL", streak=0):
    return {"diagnostics": {"status": d},
            "operations": {"status": o, "consecutive_failures": streak}}

class OperationsAlertsTests(unittest.TestCase):
    def test_clear_not_trading_approval(self):
        result = evaluate(data())
        self.assertEqual(result["severity"], "INFO")
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["auto_remediation"])

    def test_diagnostics_blocked(self):
        result = evaluate(data(d="BLOCKED"))
        self.assertEqual(result["severity"], "CRITICAL")
        self.assertIn("DIAGNOSTICS_BLOCKED", [a["code"] for a in result["alerts"]])

    def test_missing_journal(self):
        result = evaluate(data(o="REVIEW"))
        self.assertEqual(result["severity"], "WARNING")

    def test_repeated_failures(self):
        result = evaluate(data(streak=3))
        self.assertEqual(result["severity"], "CRITICAL")
        self.assertIn("REPEATED_FAILURES", [a["code"] for a in result["alerts"]])

    def test_one_failure(self):
        self.assertEqual(evaluate(data(streak=1))["severity"], "WARNING")

    def test_invalid_counter(self):
        result = evaluate(data(streak=-2))
        self.assertIn("INVALID_FAILURE_COUNT", [a["code"] for a in result["alerts"]])

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            evaluate({"operations": {}})

    def test_real_missing_repo(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspect(repo=Path(d))
            self.assertEqual(result["severity"], "CRITICAL")
            self.assertFalse(result["live_trading_approved"])

if __name__ == "__main__":
    unittest.main()
