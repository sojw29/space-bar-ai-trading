import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from readiness_desktop_v96 import readiness_view

def readiness(status="LOCAL_REPORT_READY"):
    checks = [{"code": "C" + str(i), "status": "PASS" if status == "LOCAL_REPORT_READY" else "BLOCKED",
               "detail": "Offline local check"} for i in range(5)]
    return {"status": status, "passed": 5 if status == "LOCAL_REPORT_READY" else 0,
            "total": 5, "checks": checks}

class ReadinessDesktopTests(unittest.TestCase):
    @patch("readiness_desktop_v96.assess", return_value=readiness())
    def test_ready_does_not_approve_trading(self, _):
        result = readiness_view()
        self.assertEqual(result["status"], "LOCAL_REPORT_READY")
        self.assertFalse(result["live_trading_approved"])
        self.assertEqual(result["scope"], "LOCAL_REPORTING_ONLY")

    @patch("readiness_desktop_v96.assess", return_value=readiness("BLOCKED"))
    def test_blocked_is_preserved(self, _):
        result = readiness_view()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["passed"], 0)

    @patch("readiness_desktop_v96.assess", return_value=readiness())
    def test_all_five_checks_visible(self, _):
        result = readiness_view()
        self.assertEqual(len(result["checks"]), 5)
        self.assertEqual(result["total"], 5)

    def test_real_empty_repo_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            result = readiness_view(repo=Path(d))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["live_trading_approved"])

if __name__ == "__main__":
    unittest.main()
