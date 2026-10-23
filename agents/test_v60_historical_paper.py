"""V60 explicit offline hypothetical paper replay safety and CLI integration."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"agents"))
import space_bar_launcher
from historical_paper_replay_v60 import replay_historical_paper

def make_file(path, bars=80,gap=False):
    start=1700000100-(1700000100%300)
    with open(path,"w",newline="",encoding="utf-8") as fp:
        w=csv.writer(fp);w.writerow(["timestamp","open","high","low","close","volume"])
        for i in range(bars):
            ts=start+i*300+(300 if gap and i>=30 else 0)
            x=100+i*.1
            w.writerow([ts,x-0.2,x+0.8,x-0.7,x,55+i])

class V60PaperReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"BTC_5m.csv"
        make_file(self.path)
    def tearDown(self):
        self.tmp.cleanup()

    def test_explicit_replay_yields_only_historical_hypothetical_results(self):
        first=replay_historical_paper(self.path)
        second=replay_historical_paper(self.path)
        self.assertEqual(first,second)
        self.assertEqual(first["mode"],"EXPLICIT_HISTORICAL_PAPER_REPLAY")
        self.assertEqual(first["source"],"historical_csv_snapshot")
        self.assertFalse(first["realtime"])
        self.assertEqual(first["warmup_bars"],55)
        self.assertEqual(first["bars_used"],80)
        self.assertEqual(first["paper_bars_processed"],26)
        self.assertTrue(first["paper_only"])
        self.assertFalse(first["orders_enabled"])
        self.assertFalse(first["live_trading_approved"])
        self.assertFalse(first["independent_oos_verified"])
        self.assertEqual(first["paper_trade_event_count"],
                         first["paper_entries"]+first["paper_exits"])
        self.assertIn("HYPOTHETICAL",first["warning"])
        self.assertGreater(first["paper_equity_mark_to_close"],0)

    def test_inconsistent_or_incomplete_history_rejected(self):
        for label,n,gap in [("short",54,False),("gap",80,True)]:
            bad=Path(self.tmp.name)/(label+".csv")
            make_file(bad,bars=n,gap=gap)
            with self.subTest(label=label),self.assertRaises(ValueError):
                replay_historical_paper(bad)
        with self.assertRaises(FileNotFoundError):
            replay_historical_paper(Path(self.tmp.name)/"missing.csv")

    def test_cli_explicit_replay_does_not_open_gui_or_server(self):
        with patch.object(space_bar_launcher,"run_gui") as gui:
            from io import StringIO
            with patch("sys.stdout",new_callable=StringIO) as out:
                self.assertEqual(space_bar_launcher.main(["--paper-replay",str(self.path)]),0)
            gui.assert_not_called()
            result=json.loads(out.getvalue())
            self.assertEqual(result["mode"],"EXPLICIT_HISTORICAL_PAPER_REPLAY")
            self.assertFalse(result["orders_enabled"])

    def test_launcher_keeps_simulator_opt_in(self):
        launcher=(ROOT/"space_bar_launcher.py").read_text(encoding="utf-8")
        self.assertIn("Run historical paper replay (manual)",launcher)
        self.assertIn("executor.submit(replay_historical_paper,selected)",launcher)
        self.assertIn('paper_summary=tk.StringVar(value="PAPER · NOT RUN',launcher)
        self.assertNotIn("createOrder(",launcher)
        self.assertNotIn("start_dashboard(",launcher)

if __name__=="__main__":unittest.main(verbosity=2)
