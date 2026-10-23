"""V48 office activity remains evidence-based and fails closed."""
import unittest
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "web" / "command_center.html"

class OfficeActivityTests(unittest.TestCase):
    def setUp(self):
        self.html = HTML.read_text(encoding="utf-8")

    def test_four_phases_and_status_disclosure(self):
        for part in ('id="phase-fetching"', 'id="phase-observed"',
                     'id="phase-waiting"', 'id="phase-blocked"',
                     'id="office-phase-note"', 'function setOfficePhase(phase, note)',
                     'data-phase="BLOCKED"', "실시간으로 고민하거나 실행 중이라는 뜻은 아닙니다"):
            self.assertIn(part, self.html)

    def test_poll_and_live_freshness_checks(self):
        for part in ('setOfficePhase("FETCHING"', 'setOfficePhase("OBSERVED"',
                     'setOfficePhase("WAITING"', 'setOfficePhase("BLOCKED"',
                     'if(data.realtime && (ageMinutes<0||ageMinutes>12))',
                     'latestEvents.clear()', 'resetRoom("데이터 수신 실패")'):
            self.assertIn(part, self.html)

    def test_existing_ui_and_read_only_guards(self):
        for part in ('id="inspector-panel"', 'id="paper-monitor-panel"',
                     'id="paper-analytics-panel"', 'id="consensus-panel"',
                     'PAPER RESEARCH ONLY', 'data.realtime',
                     'event.key==="Enter"||event.key===" "',
                     "prefers-reduced-motion:reduce"):
            self.assertIn(part, self.html)
        for unsafe in ('innerHTML=', 'fetch("/api/v1/orders"', '<iframe',
                       'WebSocket("'):
            self.assertNotIn(unsafe, self.html)

if __name__=="__main__":
    unittest.main(verbosity=2)
