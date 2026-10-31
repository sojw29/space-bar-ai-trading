import unittest
from pathlib import Path

ROOM=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text(encoding="utf-8")

class RoomIndicatorTests(unittest.TestCase):
    def test_room_fetches_optional_public_indicators(self):
        self.assertIn('fetch("./ohlcv_indicators.json"',ROOM)
        self.assertIn('id="v226-indicator-panel"',ROOM)
        self.assertIn('refresh.addEventListener("click",load)',ROOM)
    def test_rejects_unsafe_or_stale_data(self):
        for marker in ('data.orders_enabled!==false','data.realtime!==false',
                       'data.ai_agents_running!==false','data.trade_signals_available!==false',
                       'age>8*3600000','matches.length!==1','rows.replaceChildren()'):
            self.assertIn(marker,ROOM)
    def test_not_real_ai(self):
        self.assertIn("실시간/AI 판단/매매 신호 아님",ROOM)
        self.assertNotIn("eval(",ROOM)
if __name__=="__main__":unittest.main()
