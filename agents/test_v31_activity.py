"""V31 visual state contract tests. CI also checks JS syntax with Node."""
import unittest
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "web" / "command_center.html"


class ActivityTests(unittest.TestCase):
    def test_activity_indicators_exist(self):
        html = HTML.read_text(encoding="utf-8")
        for marker in ('id="risk-state"', 'id="observation-age"', 'id="feed-state"',
                       "station.activity.textContent", "resetRoom(", "classList.add(\"veto\")"):
            self.assertIn(marker, html)

    def test_commander_is_risk_source(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn('const veto=commanderEvent&&commanderEvent.risk_veto===true;', html)
        self.assertNotIn('const veto=apex&&apex.risk_veto===true;', html)

    def test_no_false_realtime_or_live_trading(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn("과거 데이터 · 실시간 아님", html)
        self.assertIn("거래 승인 아님", html)
        self.assertIn("PAPER RESEARCH ONLY", html)
        self.assertIn("resetRoom(\"데이터 수신 실패\")", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
