"""V62 fixed-rule chronological paper holdout, negative integrity and CLI tests."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from io import StringIO

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"agents"))
import space_bar_launcher
from chronological_holdout_v62 import (
    evaluate_chronological_holdout, read_btc_history, MIN_BARS, WARMUP
)

def fixture(path,n=240, *, gap=False, invalid=False, future=False):
    start=1700000100-(1700000100%300)
    if future:
        import time
        start=(int(time.time())//300)*300-(n-2)*300
    with open(path,"w",newline="",encoding="utf-8") as fp:
        w=csv.writer(fp);w.writerow(("timestamp","open","high","low","close","volume"))
        for i in range(n):
            ts=start+i*300+(300 if gap and i>=80 else 0)
            p=100+i*.16
            w.writerow((ts,p-.1,p+.8,p-.9,(-10 if invalid and i==100 else p),120+i))

class HoldoutV62Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.csv=Path(self.temp.name)/"btc.csv"
        fixture(self.csv)
    def tearDown(self): self.temp.cleanup()

    def test_chronological_separation_and_holdout_mark_evidence(self):
        a=evaluate_chronological_holdout(self.csv)
        b=evaluate_chronological_holdout(self.csv)
        self.assertEqual(a,b)
        self.assertEqual(a["mode"],"CHRONOLOGICAL_DESCRIPTIVE_PAPER_HOLDOUT")
        self.assertEqual(a["data_candles"],240)
        self.assertEqual(a["split_index"],168)
        self.assertEqual(a["development"]["scheduled_bars"],168-54)
        self.assertEqual(a["holdout"]["scheduled_bars"],72)
        self.assertLess(a["development"]["last_evaluated_bar_utc"],
                        a["holdout"]["first_evaluated_bar_utc"])
        self.assertEqual(a["holdout"]["paper_initial_cash"],10000)
        self.assertFalse(a["model_fitting_performed"])
        self.assertTrue(a["rule_parameters_frozen"])
        self.assertFalse(a["independent_oos_verified"])
        self.assertFalse(a["oos_validated"])
        self.assertFalse(a["orders_enabled"])
        self.assertFalse(a["realtime"])
        self.assertTrue(a["holdout"]["insufficient_closed_trade_sample"])
        self.assertIsNone(a["holdout"]["paper_win_rate_pct"])
        self.assertEqual(len(a["holdout"]["equity_curve"]),a["holdout"]["evaluated_bars"])

    def test_breaks_invalid_missing_future_and_truncation(self):
        cases=(("gap",dict(gap=True)),("bad",dict(invalid=True)),
               ("future",dict(future=True)),("short",dict(n=180)),
               ("too_many",dict(n=5001)))
        for label,args in cases:
            path=Path(self.temp.name)/(label+".csv")
            fixture(path,**args)
            with self.subTest(label=label),self.assertRaises(ValueError):
                evaluate_chronological_holdout(path)

    def test_cli_is_research_only_and_starts_no_gui(self):
        with patch.object(space_bar_launcher,"run_gui") as gui:
            with patch("sys.stdout",new_callable=StringIO) as out:
                rc=space_bar_launcher.main(["--holdout-report",str(self.csv)])
            self.assertEqual(rc,0)
            gui.assert_not_called()
        result=json.loads(out.getvalue())
        self.assertFalse(result["orders_enabled"])
        self.assertEqual(result["holdout"]["scheduled_bars"],72)
        self.assertIn("Evaluate chronological holdout (manual)",
                      (ROOT/"space_bar_launcher.py").read_text(encoding="utf-8"))

if __name__=="__main__":unittest.main(verbosity=2)
