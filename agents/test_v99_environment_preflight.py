import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from environment_preflight_v99 import preflight

class EnvironmentPreflightTests(unittest.TestCase):
    def test_actual_repository_environment(self):
        result = preflight()
        self.assertEqual(result["status"], "ENVIRONMENT_PASS", result)
        self.assertEqual(result["passed"], result["total"])
        self.assertFalse(result["live_trading_approved"])
        self.assertEqual(result["scope"], "LOCAL_DESKTOP_PREFLIGHT_ONLY")

    def test_empty_repository_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            result = preflight(repo=Path(d))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertLess(result["passed"], result["total"])

    @patch("environment_preflight_v99.importlib.util.find_spec", return_value=None)
    def test_missing_standard_module_blocks(self, _):
        self.assertEqual(preflight()["status"], "BLOCKED")

    @patch("environment_preflight_v99.platform.system", return_value="UnknownOS")
    def test_unsupported_os_blocks(self, _):
        self.assertEqual(preflight()["status"], "BLOCKED")

    def test_all_results_are_sanitized(self):
        result = preflight()
        for item in result["checks"]:
            self.assertEqual(set(item), {"code", "status", "detail"})
            self.assertIn(item["status"], ("PASS", "BLOCKED"))

if __name__ == "__main__":
    unittest.main()
