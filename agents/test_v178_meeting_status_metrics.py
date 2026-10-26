"""V178 meeting event count UI contract."""
import unittest
from pathlib import Path


class MeetingMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_metrics_are_bounded_observations(self):
        for token in ('id="v178-meeting-metrics"', 'historyEntries.filter(item=>item.state.startsWith("BLOCKED"))', 'historyEntries.filter(item=>item.state.includes("VERIFIED")', 'historyEntries.filter(item=>item.state.includes("WAIT"))', 'updateMeetingMetrics();', '거래 성과 아님', 'historyEntries.length>20'):
            self.assertIn(token, self.html)

    def test_count_categories_are_not_misrepresented_as_exclusive(self):
        self.assertIn('중복 분류 가능', self.html)
        self.assertIn('브라우저 관측 이벤트 ', self.html)


if __name__ == "__main__":
    unittest.main()
