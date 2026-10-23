"""V44 observed simulated-paper analytics, no orders or network."""
import sys
import tempfile
import unittest
import json
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_journal_v43 import PaperJournal
from paper_analytics_v44 import analyze_session
from dashboard_api_v28 import make_handler

def sample(cash, equity, count, stale=False, state="SIMULATING"):
    return {"mode":"LOCAL_PAPER_SIMULATION","schema_version":"42.0",
            "paper_only":True,"orders_enabled":False,"live_trading_approved":False,
            "paper_cash":cash,"paper_realized_net":cash-10000,
            "paper_mark_to_close_equity":equity,"mark_is_stale":stale,
            "paper_trade_event_count":count,"state":state,"position":None}

class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.journal=PaperJournal(Path(self.tmp.name)/"journal.sqlite3")
    def tearDown(self):self.tmp.cleanup()
    def test_empty_session(self):
        result=analyze_session(self.journal.path,self.journal.session_id)
        self.assertIsNone(result["observed_equity_max_drawdown_pct"])
        self.assertEqual(result["journal_entries"],0)
    def test_drawdown_ignores_stale_marks(self):
        self.journal.append("paper_snapshot",sample(10000,10000,1))
        self.journal.append("paper_snapshot",sample(10100,10200,2))
        self.journal.append("paper_snapshot",sample(9900,9999,3,True))
        self.journal.append("feed_halt",sample(9900,None,3,True,"HALTED"))
        result=analyze_session(self.journal.path,self.journal.session_id)
        self.assertEqual(result["observed_equity_points"],2)
        self.assertEqual(result["observed_equity_max_drawdown_pct"],0.0)
        self.assertEqual(result["halt_count_in_sample"],1)
        self.assertEqual(result["paper_trade_events"],3)
        self.assertFalse(result["orders_enabled"])
    def test_observed_drawdown(self):
        for equity in (10000,12000,9000):
            self.journal.append("paper_snapshot",sample(equity,equity,1))
        result=analyze_session(self.journal.path,self.journal.session_id)
        self.assertEqual(result["observed_equity_max_drawdown_pct"],25.0)
    def test_detect_nonmonotonic_trade_counter(self):
        self.journal.append("paper_snapshot",sample(10000,10000,3))
        self.journal.append("paper_snapshot",sample(10000,10000,2))
        with self.assertRaises(ValueError):
            analyze_session(self.journal.path,self.journal.session_id)
    def test_readonly_api_and_opt_out(self):
        srv=ThreadingHTTPServer(("127.0.0.1",0),
            make_handler(Path("/missing.csv"),paper_journal=self.journal))
        th=threading.Thread(target=srv.serve_forever,daemon=True);th.start()
        try:
            url="http://127.0.0.1:%d/api/v1/paper/analytics" % srv.server_port
            with urlopen(url,timeout=3) as response:
                data=json.load(response)
                self.assertEqual(data["mode"],"SIMULATED_PAPER_ANALYTICS")
            from urllib.request import Request
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url,method="POST",data=b"{}"),timeout=3)
            self.assertEqual(error.exception.code,405)
        finally:
            srv.shutdown();srv.server_close();th.join(timeout=2)

if __name__=="__main__":unittest.main(verbosity=2)
