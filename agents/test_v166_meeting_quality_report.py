"""Offline regression tests for V166 meeting report."""
import json
import tempfile
import unittest
from pathlib import Path
from meeting_quality_report_v166 import build_report


class MeetingReportTests(unittest.TestCase):
    def test_missing_quality_blocks_meeting(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build_report(Path(directory) / "missing.json")
            self.assertEqual(report["agents"]["COMMANDER"]["decision"], "WAIT")
            self.assertEqual(report["agents"]["GUARDIAN"]["state"], "VETO")
            self.assertFalse(report["orders_enabled"])

    def test_verified_quality_is_still_research_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quality.json"
            path.write_text(json.dumps({
                "overall_status": "PASS", "research_usable": True,
                "results": [{"status": "PASS", "research_usable": True} for _ in range(9)],
            }), encoding="utf-8")
            report = build_report(path)
            self.assertEqual(report["agents"]["ATLAS"]["state"], "DATA_VERIFIED")
            self.assertEqual(report["agents"]["GUARDIAN"]["state"], "CLEAR")
            self.assertEqual(report["agents"]["COMMANDER"]["decision"], "WAIT")
            self.assertFalse(report["live_trading_approved"])


if __name__ == "__main__":
    unittest.main()
