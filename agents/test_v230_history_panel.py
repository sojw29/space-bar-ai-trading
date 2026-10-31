import unittest
from pathlib import Path
ROOM=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text(encoding="utf-8")
class HistoryPanelTests(unittest.TestCase):
 def test_local_only_and_bounded(self):
  for marker in ('id="v230-history-panel"','spacebar.v230.commander.research.v1',
    'localStorage.setItem(KEY','localStorage.removeItem(KEY)','slice(-30)',
    '이 브라우저에만 저장','서버 동기화/백테스트 아님'):
   self.assertIn(marker,ROOM)
 def test_rejects_unsafe_or_stale(self):
  for marker in ('d.orders_enabled!==false','d.ai_agents_running!==false',
    'd.trade_signals_available!==false','d.backtest_verified!==false',
    'age>8*3600000','matches.length===1','d.markets.some(m=>m.risk_status'):
   self.assertIn(marker,ROOM)
 def test_no_duplicate_timestamps(self):
  self.assertIn('history.some(e=>e.timestamp===entry.timestamp)',ROOM)
if __name__=="__main__":unittest.main()
