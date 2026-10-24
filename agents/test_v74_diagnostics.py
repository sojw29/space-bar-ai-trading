import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from one_command_diagnostics_v74 import diagnose

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
ENV = {"status": "ENVIRONMENT_READY"}
RESEARCH = {"status": "OBSERVATION_READY"}

class OneCommandTests(unittest.TestCase):
    @patch("one_command_diagnostics_v74.snapshot", return_value=RESEARCH)
    @patch("one_command_diagnostics_v74.inspect_environment", return_value=ENV)
    def test_all_pass(self, env, research):
        with tempfile.TemporaryDirectory() as d:
            result = diagnose(Path(d), now=NOW)
            self.assertEqual(result["status"], "LOCAL_DIAGNOSTICS_PASS")
            self.assertFalse(result["live_trading_approved"])

    @patch("one_command_diagnostics_v74.snapshot", return_value=RESEARCH)
    @patch("one_command_diagnostics_v74.inspect_environment", return_value={"status": "BLOCKED"})
    def test_environment_blocked(self, env, research):
        self.assertEqual(diagnose(Path("."), now=NOW)["status"], "BLOCKED")

    @patch("one_command_diagnostics_v74.snapshot", return_value={"status": "BLOCKED"})
    @patch("one_command_diagnostics_v74.inspect_environment", return_value=ENV)
    def test_research_blocked(self, env, research):
        self.assertEqual(diagnose(Path("."), now=NOW)["status"], "BLOCKED")

    @patch("one_command_diagnostics_v74.snapshot", return_value={"status": "REVIEW"})
    @patch("one_command_diagnostics_v74.inspect_environment", return_value=ENV)
    def test_research_review(self, env, research):
        self.assertEqual(diagnose(Path("."), now=NOW)["status"], "REVIEW")

    def test_empty_repo_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            result = diagnose(Path(d), now=NOW)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("RESEARCH_BLOCKED", result["blockers"])

if __name__ == "__main__":
    unittest.main()
