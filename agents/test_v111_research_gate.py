import csv
import tempfile
import unittest
from pathlib import Path
from research_gate_v111 import evaluate, run

def stability(sufficient=True, positive=0.75, mean=1.0, drawdown=5.0):
    return {"version":"V110.0","strategies":[{
        "strategy":"EMA_CROSS","validation_folds":4,"total_validation_trades":160,
        "sample_sufficient":sufficient,"positive_fold_fraction":positive,
        "mean_fold_return_pct":mean,"worst_fold_max_drawdown_pct":drawdown
    }]}

class ResearchGateTests(unittest.TestCase):
    def test_candidate_is_not_live_approval(self):
        result = evaluate(stability())
        self.assertEqual(result["strategies"][0]["status"], "HUMAN_REVIEW_CANDIDATE")
        self.assertFalse(result["strategies"][0]["live_trading_approved"])
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["validated_edge"])

    def test_insufficient_sample_fails_closed(self):
        result = evaluate(stability(sufficient=False))
        self.assertEqual(result["strategies"][0]["status"], "INSUFFICIENT_OR_UNFAVORABLE_EVIDENCE")

    def test_unfavorable_fold_performance(self):
        result = evaluate(stability(positive=0.25))
        self.assertEqual(result["strategies"][0]["status"], "INSUFFICIENT_OR_UNFAVORABLE_EVIDENCE")

    def test_high_drawdown_fails(self):
        result = evaluate(stability(drawdown=25))
        self.assertEqual(result["strategies"][0]["status"], "INSUFFICIENT_OR_UNFAVORABLE_EVIDENCE")

    def test_invalid_threshold_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_REVIEW_THRESHOLDS"):
            evaluate(stability(), min_positive_fraction=float("nan"))

    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"history.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp","open","high","low","close","volume"])
                for i in range(480):
                    p = 100+0.02*i+(3 if (i//20)%2 else -3)
                    writer.writerow([1700000000000+i*300000,p,p+1,p-1,p,100])
            result = run(path)
            self.assertEqual(len(result["strategies"]), 3)
            self.assertFalse(result["orders_enabled"])

if __name__ == "__main__":
    unittest.main()
