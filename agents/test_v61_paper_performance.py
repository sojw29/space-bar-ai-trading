"""V61 descriptive in-sample simulated-paper reporting and no-order guard."""
import csv
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from io import StringIO

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"agents"))
import space_bar_launcher
from historical_paper_replay_v60 import replay_historical_paper
from paper_performance_v61 import analyze_paper_evidence,report_historical_paper

def history(path,n=80):
    start=1700000100-(1700000100%300)
    with open(path,"w",newline="",encoding="utf-8") as file:
        writer=csv.writer(file);writer.writerow(["timestamp","open","high","low","close","volume"])
        for i in range(n):
            price=100+i*.13
            writer.writerow([start+i*300,price-.2,price+.8,price-.9,price,100+i])

class V61PaperPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.file=Path(self.tmp.name)/"btc.csv"
        history(self.file)
    def tearDown(self):
        self.tmp.cleanup()

    def test_descriptive_report_is_stable_and_not_verified(self):
        report=report_historical_paper(self.file)
        self.assertEqual(report,report_historical_paper(self.file))
        self.assertEqual(report["mode"],"DESCRIPTIVE_HISTORICAL_PAPER_PERFORMANCE")
        self.assertFalse(report["realtime"])
        self.assertTrue(report["paper_only"])
        self.assertFalse(report["orders_enabled"])
        self.assertFalse(report["live_trading_approved"])
        self.assertFalse(report["oos_validated"])
        self.assertFalse(report["performance_sample_sufficient"])
        self.assertIsNone(report["paper_win_rate_pct"])
        self.assertIsNone(report["paper_profit_factor"])
        self.assertEqual(len(report["equity_curve"]),26)
        self.assertEqual(report["observed_paper_points"],26)
        self.assertGreaterEqual(report["paper_max_observed_drawdown_pct"],0)
        self.assertEqual(report["paper_latest_marked_equity"],
                         report["equity_curve"][-1]["paper_equity"])
        self.assertIn("IN-SAMPLE",report["warning"])

    def test_tampered_equity_and_broker_flags_fail_closed(self):
        replay=replay_historical_paper(self.file,include_evidence=True)
        for field,value in [("orders_enabled",True),("paper_only",False),
                            ("realtime",True),("independent_oos_verified",True)]:
            bad=deepcopy(replay);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                analyze_paper_evidence(bad)
        bad=deepcopy(replay);bad["_completed_candle_equity_observations"][0]["equity"]=float("nan")
        with self.assertRaises(ValueError):analyze_paper_evidence(bad)
        bad=deepcopy(replay);bad["_completed_candle_equity_observations"][1]["timestamp"]+=300
        with self.assertRaises(ValueError):analyze_paper_evidence(bad)
        bad=deepcopy(replay);bad["paper_trade_event_count"]+=1
        with self.assertRaises(ValueError):analyze_paper_evidence(bad)

    def test_drawdown_sample_and_closed_trade_math_without_winrate_claim(self):
        replay=replay_historical_paper(self.file,include_evidence=True)
        replay["_completed_candle_equity_observations"]=[
            {"timestamp":1700000100-(1700000100%300)+i*300,
             "equity": equity,"cash":equity,"close":100,"position":None}
            for i,equity in enumerate([10000,11000,8800])]
        replay["paper_bars_processed"]=3
        replay["paper_equity_mark_to_close"]=8800
        replay["_hypothetical_trade_events"]=[]
        replay["paper_trade_event_count"]=0
        replay["paper_entries"]=replay["paper_exits"]=0
        replay["paper_position"]=None
        report=analyze_paper_evidence(replay)
        self.assertEqual(report["paper_max_observed_drawdown_pct"],20)
        self.assertIsNone(report["paper_win_rate_pct"])

    def test_cli_outputs_json_without_starting_service(self):
        with patch.object(space_bar_launcher,"run_gui") as gui:
            with patch("sys.stdout",new_callable=StringIO) as out:
                self.assertEqual(space_bar_launcher.main(["--paper-report",str(self.file)]),0)
            gui.assert_not_called()
        self.assertFalse(json.loads(out.getvalue())["orders_enabled"])
        source=(ROOT/"space_bar_launcher.py").read_text(encoding="utf-8")
        self.assertIn('Analyze paper performance (manual)',source)
        self.assertIn('executor.submit(report_historical_paper,selected)',source)

if __name__=="__main__":unittest.main(verbosity=2)
