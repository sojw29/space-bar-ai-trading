import json
import tempfile
import unittest
from pathlib import Path
from drift_diagnostics_v126 import diagnose,run

def snapshot(mean=2,dd=4,rate=80,sells=50,folds=10,abstained=0,hash_="abc"):
    return {"label":hash_,"report_sha256":hash_,"metrics":{
        "evaluated_folds":folds,"abstained_folds":abstained,
        "positive_fold_rate_pct":rate,"mean_fold_return_pct":mean,
        "worst_fold_return_pct":-2,
        "worst_fold_max_drawdown_pct":dd,
        "hypothetical_sell_events":sells}}

class DriftDiagnosticsTests(unittest.TestCase):
    def test_insufficient_data(self):
        self.assertEqual(diagnose([])["status"],"INSUFFICIENT_COMPARISON_DATA")
    def test_return_change_explained(self):
        result=diagnose([snapshot(),snapshot(mean=-1,hash_="def")])
        self.assertIn("mean_fold_return_pct",[x["metric"] for x in result["possible_contributors"]])
    def test_trade_count_change(self):
        result=diagnose([snapshot(),snapshot(sells=20,hash_="def")])
        self.assertIn("hypothetical_sell_events",[x["metric"] for x in result["possible_contributors"]])
    def test_drawdown_change(self):
        result=diagnose([snapshot(),snapshot(dd=10,hash_="def")])
        self.assertIn("worst_fold_max_drawdown_pct",[x["metric"] for x in result["possible_contributors"]])
    def test_fold_coverage_change(self):
        result=diagnose([snapshot(),snapshot(folds=6,hash_="def")])
        self.assertIn("evaluated_folds",[x["metric"] for x in result["possible_contributors"]])
    def test_no_causality_claim(self):
        result=diagnose([snapshot(),snapshot(mean=-1,hash_="def")])
        self.assertFalse(result["causality_established"])
        self.assertFalse(result["market_regime_change_verified"])
    def test_no_orders(self):
        result=diagnose([snapshot(),snapshot(hash_="def")])
        self.assertFalse(result["live_trading_approved"])
        self.assertEqual(result["orders_submitted_to_exchange"],0)
    def test_identical_metrics(self):
        result=diagnose([snapshot(),snapshot(hash_="def")])
        self.assertEqual(result["metric_changes_count"],0)
    def test_determinism(self):
        data=[snapshot(),snapshot(mean=-1,hash_="def")]
        self.assertEqual(diagnose(data),diagnose(data))
    def test_invalid_history(self):
        with self.assertRaisesRegex(ValueError,"INVALID_HISTORY"):
            diagnose({})
    def test_json_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"history.json"
            path.write_text(json.dumps([snapshot(),snapshot(mean=-1,hash_="def")]),encoding="utf-8")
            self.assertEqual(run(path)["version"],"V126.0")

if __name__=="__main__":
    unittest.main()
