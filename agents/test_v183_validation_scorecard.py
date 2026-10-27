"""V183 offline validation scorecard contract."""
import unittest
from pathlib import Path


class ValidationScorecardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_seven_explicit_checks(self):
        for token in ('id="v183-validation-scorecard"', 'const checks=[', 'gate.quality_status==="PASS"', 'gate.risk_veto===false', 'meeting.agents.ATLAS.state==="DATA_VERIFIED"', 'meeting.agents.GUARDIAN.state==="CLEAR"', 'meeting.agents.COMMANDER.decision==="WAIT"', 'meeting.orders_enabled===false', 'meeting.live_trading_approved===false'):
            self.assertIn(token, self.html)

    def test_fail_closed_and_limited_claim(self):
        for token in ('const status=passed===checks.length?"VERIFIED":"BLOCKED / INCOMPLETE";', '검증 스코어카드 · ', '거래 성과 아님', 'renderValidationScorecard();'):
            self.assertIn(token, self.html)


if __name__ == "__main__":
    unittest.main()
