"""V179 meeting timeline presentation contract."""
import unittest
from pathlib import Path


class MeetingTimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_accessible_timeline(self):
        for token in ('id="v179-meeting-timeline"', 'id="v179-timeline-bars"', 'role="img"', 'timelineBars.setAttribute("aria-label"', 'bar.title=item.time+" · "+item.state+" · "+item.source;'):
            self.assertIn(token, self.html)

    def test_only_observed_bounded_events(self):
        for token in ('const events=historyEntries.slice().reverse();', 'timelineBars.replaceChildren();', 'renderMeetingTimeline();', 'historyEntries.length>20', '거래 성과 아님'):
            self.assertIn(token, self.html)

    def test_blocked_visual_priority(self):
        self.assertIn('const blocked=item.state.startsWith("BLOCKED");', self.html)
        self.assertIn('const verified=item.state.includes("VERIFIED")&&!blocked;', self.html)


if __name__ == "__main__":
    unittest.main()
