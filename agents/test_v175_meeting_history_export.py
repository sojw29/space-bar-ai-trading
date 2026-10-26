"""V175 read-only local history export contract."""
import unittest
from pathlib import Path


class HistoryExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_local_json_download(self):
        for token in ('id="v175-export-meeting-history"', 'URL.createObjectURL(blob)', 'anchor.download="spacebar-meeting-ui-history.json"', 'URL.revokeObjectURL(url)', 'application/json'):
            self.assertIn(token, self.html)

    def test_no_audit_or_execution_claim(self):
        for token in ('mode:"browser_observed_ui_events"', 'research_only:true', 'orders_enabled:false', 'persistent_audit:false', 'events:historyEntries.map(item=>({...item}))'):
            self.assertIn(token, self.html)


if __name__ == "__main__":
    unittest.main()
