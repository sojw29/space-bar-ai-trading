import json
import tempfile
import unittest
from pathlib import Path
from performance_drift_alerts_v125 import detect,run

def snapshot(mean=2,dd=4,rate=80,folds=10,hash_="abc"):
    return {"report_sha256":hash_,"metrics":{
        "evaluated_folds":folds,"abstained_folds":0,
        "positive_fold_rate_pct":rate,"mean_fold_return_pct":mean,
        "worst_fold_return_pct":-2,
        "worst_fold_max_drawdown_pct":dd,
        "hypothetical_sell_events":50}}

def codes(result):
    return [w["code"] for w in result["warnings"]]

class PerformanceDriftTests(unittest.TestCase):
    def test_no_history(self):
        self.assertIn("INSUFFICIENT_HISTORY",codes(detect([])))
    def test_one_snapshot(self):
        self.assertIn("INSUFFICIENT_HISTORY",codes(detect([snapshot()])))
    def test_return_deterioration(self):
        self.assertIn("MEAN_FOLD_RETURN_DETERIORATION",
                      codes(detect([snapshot(),snapshot(mean=-1,hash_="def")])))
    def test_drawdown_deterioration(self):
        self.assertIn("DRAWDOWN_DETERIORATION",
                      codes(detect([snapshot(),snapshot(dd=10,hash_="def")])))
    def test_positive_rate_deterioration(self):
        self.assertIn("POSITIVE_FOLD_RATE_DETERIORATION",
                      codes(detect([snapshot(),snapshot(rate=50,hash_="def")])))
    def test_low_folds(self):
        self.assertIn("INSUFFICIENT_FOLDS",
                      codes(detect([snapshot(folds=3),snapshot(hash_="def")])))
    def test_no_approval(self):
        result=detect([snapshot(),snapshot(hash_="def")])
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["performance_drift_proven"])
        self.assertFalse(result["automatic_strategy_changes"])
    def test_same_report(self):
        self.assertIn("SAME_REPORT_RECORDED",codes(detect([snapshot(),snapshot()])))
    def test_invalid_threshold(self):
        with self.assertRaisesRegex(ValueError,"INVALID_THRESHOLDS"):
            detect([],return_drop_pp=-1)
    def test_invalid_metric(self):
        with self.assertRaisesRegex(ValueError,"INVALID_MEAN_FOLD_RETURN_PCT"):
            detect([snapshot(),snapshot(mean=float("nan"),hash_="def")])
    def test_json_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"history.json"
            path.write_text(json.dumps([snapshot(),snapshot(mean=-1,hash_="def")]),encoding="utf-8")
            self.assertIn("MEAN_FOLD_RETURN_DETERIORATION",codes(run(path)))

if __name__=="__main__":
    unittest.main()
