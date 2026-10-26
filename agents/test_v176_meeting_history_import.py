"""V176 local JSON import safety contract."""
import unittest
from pathlib import Path


class MeetingImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_file_only_and_strict_shape(self):
        for token in ('id="v176-import-meeting-history"', 'file.size>65536', 'payload.version!=="V175.0"', 'payload.mode!=="browser_observed_ui_events"', 'payload.events.length>20', 'payload.orders_enabled!==false', 'payload.persistent_audit!==false'):
            self.assertIn(token, self.html)

    def test_untrusted_text_not_interpreted_as_html(self):
        self.assertIn('line.textContent=item.time+" · "+item.state+" · "+item.source;', self.html)
        self.assertIn('summary.textContent="불러온 과거 UI 기록 보기";', self.html)
        self.assertIn('event.target.value="";', self.html)

    def test_import_does_not_modify_current_decision(self):
        self.assertIn('현재 판단과 무관', self.html)
        self.assertIn('불러오기 거부', self.html)
        self.assertIn('details.id="v176-imported-history";', self.html)


if __name__ == "__main__":
    unittest.main()
