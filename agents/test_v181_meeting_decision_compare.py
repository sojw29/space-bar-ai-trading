"""V181 observed meeting verdict comparison contract."""
import unittest
from pathlib import Path


class DecisionCompareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_decision_change_is_read_only(self):
        for token in ('id="v181-decision-compare"', 'function meetingDecisionLabel(state)', 'function renderDecisionCompare()', 'renderDecisionCompare();', '주문 없음'):
            self.assertIn(token, self.html)

    def test_no_invented_previous_verdict(self):
        for token in ('historyEntries.find(item=>current&&meetingDecisionLabel(item.state)!==meetingDecisionLabel(current.state))', '비교할 다른 상태 없음', '관측 없음'):
            self.assertIn(token, self.html)

    def test_safe_rendering(self):
        self.assertIn('decisionCompare.textContent=', self.html)
        self.assertNotIn('decisionCompare.innerHTML=', self.html)


if __name__ == "__main__":
    unittest.main()
