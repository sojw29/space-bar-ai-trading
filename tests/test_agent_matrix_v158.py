"""V158: read-only, fail-closed agent matrix guardrails."""
import unittest
from pathlib import Path


class AgentMatrixTests(unittest.TestCase):
    def test_agent_matrix_uses_only_verified_events(self):
        html=(Path(__file__).resolve().parents[1]/"web"/"office_3d.html").read_text(encoding="utf-8")
        self.assertIn('id="v158-agent-matrix"',html)
        self.assertIn("function renderAgentMatrix()",html)
        self.assertIn("const record=hasValid?events.get(id):null;",html)
        self.assertIn('value.textContent=record?record.decision+" · 완료 봉 연구":"OFFLINE · 검증 이벤트 없음";',html)
        self.assertIn('function renderInspector(){\n renderAgentMatrix();',html)
        self.assertIn('container.replaceChildren();',html)


if __name__=="__main__":
    unittest.main()
