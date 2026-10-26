"""V177 local meeting event filtering contract."""
import unittest
from pathlib import Path


class MeetingHistoryFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_filter_controls(self):
        for token in ('id="v177-history-filter"', 'value="ALL"', 'value="BLOCKED"', 'value="VERIFIED"', 'value="WAIT"', 'historyFilter.addEventListener("change",renderMeetingHistory)'):
            self.assertIn(token, self.html)

    def test_filter_only_observed_events(self):
        for token in ('historyEntries.filter(item=>', 'history.replaceChildren();', 'row.textContent=item.time+" · "+item.state+" · "+item.source;', 'renderMeetingHistory();', 'historyEntries.length>20'):
            self.assertIn(token, self.html)

    def test_no_data_fallback(self):
        self.assertIn('history.textContent="선택한 조건의 기록 없음";', self.html)


if __name__ == "__main__":
    unittest.main()
