"""V159: agent matrix selection uses existing read-only inspector."""
import unittest
from pathlib import Path

class AgentSelectionTests(unittest.TestCase):
    def test_matrix_selects_inspector(self):
        html=(Path(__file__).resolve().parents[1]/"web"/"office_3d.html").read_text(encoding="utf-8")
        section=html.split("function renderAgentMatrix(){",1)[1].split("function renderInspector(){",1)[0]
        for expected in ('select.type="button"', 'select.textContent="분석 근거 보기"',
                         'select.addEventListener("click",()=>selectAgent(id))',
                         'select.setAttribute("aria-pressed",String(selected===id))',
                         'value.title=record?String(record.reason||"근거 없음")'):
            self.assertIn(expected,section)
        self.assertIn('const data=hasValid?events.get(selected):null;',html)

if __name__=="__main__":
    unittest.main()
