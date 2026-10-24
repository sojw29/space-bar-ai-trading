import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pc_readiness_v75 import checklist

def diagnostic(status="BLOCKED", env_status="REVIEW", research_status="BLOCKED",
               python_ok=True, agents=True, cli=True, reports=False):
    return {"status": status, "environment": {"status": env_status,
        "checks": {"python_supported": python_ok, "agents_directory_exists": agents,
                   "v72_cli_exists": cli, "reports_dir_exists": reports}},
        "research": {"status": research_status}}

class ReadinessTests(unittest.TestCase):
    @patch("pc_readiness_v75.diagnose", return_value=diagnostic())
    def test_missing_reports_guidance(self, _):
        result = checklist(Path("."))
        self.assertTrue(any("Generate offline" in x for x in result["next_steps"]))
        self.assertFalse(result["live_trading_approved"])

    @patch("pc_readiness_v75.diagnose", return_value=diagnostic(python_ok=False))
    def test_old_python_guidance(self, _):
        self.assertTrue(any("Python 3.11+" in x for x in checklist(Path("."))["next_steps"]))

    @patch("pc_readiness_v75.diagnose", return_value=diagnostic(agents=False))
    def test_wrong_repo_guidance(self, _):
        self.assertTrue(any("repository folder" in x for x in checklist(Path("."))["next_steps"]))

    @patch("pc_readiness_v75.diagnose", return_value=diagnostic(
        status="LOCAL_DIAGNOSTICS_PASS", env_status="ENVIRONMENT_READY",
        research_status="OBSERVATION_READY", reports=True))
    def test_ready_is_paper_only(self, _):
        result = checklist(Path("."))
        self.assertEqual(result["status"], "LOCAL_DIAGNOSTICS_PASS")
        self.assertTrue(any("paper-only" in x for x in result["next_steps"]))

    @patch("pc_readiness_v75.diagnose", return_value=diagnostic(
        status="REVIEW", research_status="REVIEW", reports=True))
    def test_review_guidance(self, _):
        self.assertTrue(any("warnings" in x for x in checklist(Path("."))["next_steps"]))

    def test_empty_repo_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(checklist(Path(d))["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
