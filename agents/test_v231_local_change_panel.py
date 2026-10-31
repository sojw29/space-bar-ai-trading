import unittest
from pathlib import Path
ROOM=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text(encoding="utf-8")
class LocalComparisonTests(unittest.TestCase):
 def test_comparison_reads_only_local_research_history(self):
  for marker in ('id="v231-change-panel"','spacebar.v230.commander.research.v1',
    'localStorage.getItem(KEY)','unique.length<2','Date.parse(a.timestamp)-Date.parse(b.timestamp)',
    'a.trend!==b.trend','b.ratio-a.ratio','거래 신호/성과 예측 아님'):
   self.assertIn(marker,ROOM)
 def test_fails_closed_on_invalid_or_duplicate_snapshots(self):
  for marker in ('raw.length>30000','data.filter(valid)','match.length===1',
    'unique[unique.length-1].timestamp===item.timestamp','rows.replaceChildren()'):
   self.assertIn(marker,ROOM)
if __name__=="__main__":unittest.main()
