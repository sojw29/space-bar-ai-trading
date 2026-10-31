import unittest
from pathlib import Path

ROOM=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text(encoding="utf-8")
class AgentPanelTests(unittest.TestCase):
    def test_panel_fetches_published_diagnostics(self):
        self.assertIn('id="v227-agent-panel"',ROOM)
        self.assertIn('fetch("./market_diagnostics.json"',ROOM)
        self.assertIn('refresh.addEventListener("click",load)',ROOM)
    def test_fail_closed_on_stale_unsafe_or_unexpected_agent_status(self):
        for marker in ('d.orders_enabled!==false','d.ai_agents_running!==false',
                       'd.trade_signals_available!==false','age>8*3600000',
                       '"INSUFFICIENT_HISTORY"','"NO_TRADE_AUTHORIZATION"',
                       'record.status!==expectedStatus'):
            self.assertIn(marker,ROOM)
    def test_honest_non_ai_disclaimer(self):
        self.assertIn("실제 AI 실행/거래 신호 아님",ROOM)
if __name__=="__main__":unittest.main()
