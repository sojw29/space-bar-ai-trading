import json
import tempfile
import unittest
from pathlib import Path
from mobile_html_report_v88 import convert, render

def sample():
    return {"schema": "spacebar.local-status.v87",
            "generated_utc": "2026-10-24T00:00:00+00:00",
            "overall_status": "REVIEW", "pc_status": "BLOCKED",
            "audit_status": "REVIEW", "history_status": "ANALYZED",
            "recent_statuses": [{"timestamp_utc": "2026-10-24T00:00:00+00:00", "status": "BLOCKED"}],
            "status_transitions": [{"timestamp_utc": "2026-10-24T00:00:00+00:00",
                                    "from": "BLOCKED", "to": "REVIEW"}],
            "research_only": True, "live_trading_approved": False,
            "transport": "LOCAL_FILE_ONLY"}

class HtmlReportTests(unittest.TestCase):
    def test_mobile_html(self):
        page = render(sample())
        self.assertIn('name="viewport"', page)
        self.assertIn("Status transitions", page)
        self.assertIn("LIVE TRADING DISABLED", page)
        self.assertNotIn("<script", page)

    def test_invalid_schema(self):
        data = sample()
        data["schema"] = "other"
        with self.assertRaises(ValueError):
            render(data)

    def test_live_trading_flag_rejected(self):
        data = sample()
        data["live_trading_approved"] = True
        with self.assertRaises(ValueError):
            render(data)

    def test_untrusted_timestamp_escaped(self):
        data = sample()
        data["generated_utc"] = '<script>alert(1)</script>'
        self.assertNotIn("<script>", render(data))

    def test_invalid_history_rejected(self):
        data = sample()
        data["recent_statuses"] = "wrong"
        with self.assertRaises(ValueError):
            render(data)

    def test_file_conversion(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "input.json"
            target = Path(d) / "output.html"
            source.write_text(json.dumps(sample()), encoding="utf-8")
            convert(source, target)
            self.assertTrue(target.read_text(encoding="utf-8").startswith("<!doctype html>"))

    def test_oversized_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "input.json"
            source.write_bytes(b"x" * 131073)
            with self.assertRaises(ValueError):
                convert(source, Path(d) / "output.html")

if __name__ == "__main__":
    unittest.main()
