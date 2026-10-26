"""V173 read-only agent evidence inspector HTML contract."""
import unittest
from pathlib import Path


class AgentEvidenceInspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_agent_choices_and_accessibility(self):
        for token in ('id="v173-agent-select"', 'id="v173-agent-detail"', 'value="ATLAS"', 'value="GUARDIAN"', 'value="COMMANDER"', 'agentSelect.addEventListener("change",inspectAgent)'):
            self.assertIn(token, self.html)

    def test_fail_closed_and_read_only(self):
        for token in ('let latestMeeting=null;', 'latestMeeting=null;', 'inspectAgent();', 'NO VERIFIED EVIDENCE', 'RESEARCH ONLY / NO ORDERS', 'meeting.orders_enabled===false', 'meeting.live_trading_approved===false', 'meeting.research_only===true'):
            self.assertIn(token, self.html)

    def test_only_known_agent_states(self):
        for token in ('["DATA_VERIFIED","DATA_UNVERIFIED"]', '["CLEAR","VETO"]', '["WAIT"]', 'allowed.includes(value)?value:"UNVERIFIED"'):
            self.assertIn(token, self.html)


if __name__ == "__main__":
    unittest.main()
