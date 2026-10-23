"""V32 inspector contract checks: selection, voting and error fallback."""
import unittest
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "web" / "command_center.html"


class InspectorTests(unittest.TestCase):
    def test_selectable_inspector(self):
        html = HTML.read_text(encoding="utf-8")
        for phrase in ('id="inspector-panel"', 'id="inspector-confidence"',
                       'id="inspector-votes"', 'id="inspector-risk"',
                       'function selectAgent(id)', 'renderInspector();',
                       'event.key==="Enter"', 'event.key===" "'):
            self.assertIn(phrase, html)

    def test_safe_fallback_after_disconnect(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn("latestEvents.clear()", html)
        self.assertIn("lastFailure=true;", html)
        self.assertIn('renderInspector();', html)
        self.assertIn('textContent=event?String(event.reason', html)
        self.assertNotIn("innerHTML=", html)

    def test_labels_do_not_claim_validated_win_rate(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn("신뢰도는 검증된 승률이 아닙니다", html)
        self.assertIn("주관적 점수", html)
        self.assertIn("PAPER RESEARCH ONLY", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
