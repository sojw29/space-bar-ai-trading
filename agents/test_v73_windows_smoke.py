import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from windows_smoke_v73 import inspect_environment

class WindowsSmokeTests(unittest.TestCase):
    def test_repository_with_reports_ready(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "agents").mkdir()
            (root / "agents/local_status_v72.py").touch()
            (root / "reports").mkdir()
            result = inspect_environment(root)
            self.assertEqual(result["status"], "ENVIRONMENT_READY")
            self.assertFalse(result["live_trading_approved"])

    def test_missing_reports_warns_not_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "agents").mkdir()
            (root / "agents/local_status_v72.py").touch()
            result = inspect_environment(root)
            self.assertEqual(result["status"], "REVIEW")

    def test_missing_cli_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "agents").mkdir()
            self.assertIn("V72_CLI_EXISTS", inspect_environment(root)["blockers"])

    def test_missing_agents_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(inspect_environment(Path(d))["status"], "BLOCKED")

    def test_custom_reports_location(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "agents").mkdir()
            (root / "agents/local_status_v72.py").touch()
            outside = root / "separate"
            outside.mkdir()
            result = inspect_environment(root, outside)
            self.assertEqual(result["status"], "ENVIRONMENT_READY")

if __name__ == "__main__":
    unittest.main()
