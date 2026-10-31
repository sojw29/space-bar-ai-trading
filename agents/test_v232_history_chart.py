import unittest
from pathlib import Path
ROOM=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text(encoding="utf-8")
class ChartTests(unittest.TestCase):
 def test_local_only_svg_chart(self):
  for value in ('id="v232-chart-panel"','id="v232-chart"','createElementNS(NS,tag)',
    'spacebar.v230.commander.research.v1','localStorage.getItem(KEY)',
    'Date.parse(t)-start','records.slice(-30)','거래량 비율은 가격/수익률 아님'):
   self.assertIn(value,ROOM)
 def test_missing_values_break_lines(self):
  self.assertIn('if(m.ratio===null){flush();continue;}',ROOM)
 def test_reject_invalid_data(self):
  for value in ('raw.length>30000','samples.length<2','end<=start',
    'matches.length===1','Number.isFinite(matches[0].ratio)','svg.replaceChildren()'):
   self.assertIn(value,ROOM)
if __name__=="__main__":unittest.main()
