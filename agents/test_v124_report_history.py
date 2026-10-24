import json
import tempfile
import unittest
from pathlib import Path
from report_history_v124 import record, compare, _snapshot

def report(mean=1.0):
    return {"version":"V123.0","scorecard":{"version":"V121.0",
            "evaluated_folds":6,"abstained_folds":1,"positive_fold_rate_pct":70,
            "mean_fold_return_pct":mean,"worst_fold_return_pct":-2,
            "worst_fold_max_drawdown_pct":5,"hypothetical_sell_events":40}}

class ReportHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"history.json"
    def tearDown(self):
        self.tmp.cleanup()
    def save(self, value=1.0, label="run"):
        return record(report(value),self.path,label,"2026-10-24T10:00:00+09:00")
    def test_first_snapshot(self):
        self.assertEqual(self.save()["history_count"],1)
    def test_comparison_delta(self):
        self.save()
        result=self.save(2.5,"run2")
        self.assertEqual(result["comparison"]["changes"]["mean_fold_return_pct"]["delta"],1.5)
    def test_duplicate_unchanged(self):
        self.save()
        self.assertEqual(self.save()["status"],"DUPLICATE_UNCHANGED")
    def test_no_approval(self):
        self.save()
        result=self.save(2,"later")
        self.assertFalse(result["validated_edge"])
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["comparison"]["improvement_claim"])
    def test_invalid_report(self):
        with self.assertRaisesRegex(ValueError,"INVALID_V123_REPORT"):
            self.save_invalid({"version":"V122.0"})
    def save_invalid(self, value):
        return record(value,self.path,"run","2026-10-24T10:00:00+09:00")
    def test_timezone_required(self):
        with self.assertRaisesRegex(ValueError,"TIMESTAMP_MUST_HAVE_TIMEZONE"):
            record(report(),self.path,"run","2026-10-24T10:00:00")
    def test_invalid_metric(self):
        bad=report()
        bad["scorecard"]["mean_fold_return_pct"]=float("nan")
        with self.assertRaisesRegex(ValueError,"INVALID_METRIC"):
            self.save_invalid(bad)
    def test_corrupt_history(self):
        self.path.write_text("{broken",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"INVALID_HISTORY"):
            self.save()
    def test_json_persisted(self):
        self.save()
        self.assertEqual(len(json.loads(self.path.read_text(encoding="utf-8"))),1)
    def test_comparison_is_descriptive(self):
        a=_snapshot(report(1),"a")
        b=_snapshot(report(3),"b")
        self.assertFalse(compare(a,b)["comparable_configuration_verified"])

if __name__=="__main__":
    unittest.main()
