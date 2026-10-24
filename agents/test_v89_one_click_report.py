import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from one_click_report_v89 import generate

class OneClickReportTests(unittest.TestCase):
    def test_real_pipeline_missing_repo_stays_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "empty"
            repo.mkdir()
            result = generate(repo=repo, output_dir=Path(d) / "out")
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["live_trading_approved"])
            self.assertEqual(result["transport"], "LOCAL_FILE_ONLY")
            self.assertTrue(Path(result["html_path"]).exists())
            self.assertTrue(Path(result["json_path"]).exists())

    def test_html_has_no_script_or_remote_links(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "empty"
            repo.mkdir()
            result = generate(repo=repo, output_dir=Path(d) / "out")
            page = Path(result["html_path"]).read_text(encoding="utf-8")
            self.assertNotIn("<script", page)
            self.assertNotIn("http://", page)
            self.assertNotIn("https://", page)

    def test_json_and_html_consistency(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "empty"
            repo.mkdir()
            result = generate(repo=repo, output_dir=Path(d) / "out")
            payload = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(result["status"], payload["overall_status"])
            self.assertIn(payload["overall_status"],
                          Path(result["html_path"]).read_text(encoding="utf-8"))

    @patch("one_click_report_v89.convert", side_effect=ValueError("INVALID_STATUS_SCHEMA"))
    def test_converter_failure_propagates(self, _):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "empty"
            repo.mkdir()
            with self.assertRaises(ValueError):
                generate(repo=repo, output_dir=Path(d) / "out")

    def test_custom_output_directory(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "empty"
            repo.mkdir()
            target = Path(d) / "custom"
            result = generate(repo=repo, output_dir=target)
            self.assertEqual(Path(result["html_path"]).parent, target.resolve())

if __name__ == "__main__":
    unittest.main()
