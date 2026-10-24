import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from integrated_local_audit_v79 import audit

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)

def current(status):
    return {"status": status}

def history(status):
    return {"status": status}

def triage(status):
    return {"status": status}

class IntegratedAuditTests(unittest.TestCase):
    @patch("integrated_local_audit_v79.triage", return_value=triage("NO_RECORDED_ISSUES"))
    @patch("integrated_local_audit_v79.analyze", return_value=history("ANALYZED"))
    @patch("integrated_local_audit_v79.diagnose", return_value=current("LOCAL_DIAGNOSTICS_PASS"))
    def test_pass_is_not_trading_approval(self, *_):
        with tempfile.TemporaryDirectory() as d:
            result = audit(Path(d), now=NOW)
            self.assertEqual(result["status"], "LOCAL_AUDIT_PASS")
            self.assertFalse(result["live_trading_approved"])

    @patch("integrated_local_audit_v79.triage", return_value=triage("NO_RECORDED_ISSUES"))
    @patch("integrated_local_audit_v79.analyze", return_value=history("ANALYZED"))
    @patch("integrated_local_audit_v79.diagnose", return_value=current("BLOCKED"))
    def test_current_blocked(self, *_):
        self.assertEqual(audit(Path("."), now=NOW)["status"], "BLOCKED")

    @patch("integrated_local_audit_v79.triage", return_value=triage("NO_RECORDED_ISSUES"))
    @patch("integrated_local_audit_v79.analyze", return_value=history("ANALYZED"))
    @patch("integrated_local_audit_v79.diagnose", return_value=current("REVIEW"))
    def test_current_review(self, *_):
        self.assertEqual(audit(Path("."), now=NOW)["status"], "REVIEW")

    @patch("integrated_local_audit_v79.triage", return_value=triage("INSUFFICIENT_DATA"))
    @patch("integrated_local_audit_v79.analyze", return_value=history("INSUFFICIENT_DATA"))
    @patch("integrated_local_audit_v79.diagnose", return_value=current("LOCAL_DIAGNOSTICS_PASS"))
    def test_missing_history_requires_review(self, *_):
        result = audit(Path("."), now=NOW)
        self.assertEqual(result["status"], "REVIEW")
        self.assertIn("HISTORY_NOT_AVAILABLE", result["issues"])

    @patch("integrated_local_audit_v79.triage", return_value=triage("REVIEW_PRIORITIES"))
    @patch("integrated_local_audit_v79.analyze", return_value=history("ANALYZED"))
    @patch("integrated_local_audit_v79.diagnose", return_value=current("LOCAL_DIAGNOSTICS_PASS"))
    def test_historical_issues_require_review(self, *_):
        self.assertEqual(audit(Path("."), now=NOW)["status"], "REVIEW")

    def test_empty_repo_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            result = audit(Path(d), now=NOW)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["automatic_repair"])

if __name__ == "__main__":
    unittest.main()
