import csv
import tempfile
import unittest
from pathlib import Path
from walkforward_stability_v110 import analyze, run

def report():
    folds = []
    for i, ret in enumerate([2.0, -1.0, 3.0, -2.0]):
        folds.append({
            "validation_start_timestamp": str(1000+i*100),
            "validation_end_timestamp": str(1099+i*100),
            "validation": {"return": ret, "max_drawdown": 4+i, "trades": 40}
        })
    return {"version": "V109.0", "results": [{"strategy": "EMA_CROSS", "folds": folds}]}

class WalkforwardStabilityTests(unittest.TestCase):
    def test_fold_summary(self):
        result = analyze(report())["strategies"][0]
        self.assertEqual(result["positive_folds"], 2)
        self.assertEqual(result["negative_folds"], 2)
        self.assertEqual(result["mean_fold_return_pct"], 0.5)
        self.assertEqual(result["worst_fold_return_pct"], -2)
        self.assertEqual(result["total_validation_trades"], 160)
        self.assertTrue(result["sample_sufficient"])

    def test_low_sample(self):
        data = report()
        data["results"][0]["folds"][0]["validation"]["trades"] = 1
        self.assertEqual(analyze(data)["strategies"][0]["status"], "INSUFFICIENT_EVIDENCE")

    def test_overlap_rejected(self):
        data = report()
        data["results"][0]["folds"][1]["validation_start_timestamp"] = "1000"
        with self.assertRaisesRegex(ValueError, "OVERLAPPING"):
            analyze(data)

    def test_nan_rejected(self):
        data = report()
        data["results"][0]["folds"][0]["validation"]["return"] = float("nan")
        with self.assertRaisesRegex(ValueError, "NONFINITE"):
            analyze(data)

    def test_live_trading_never_approved(self):
        self.assertFalse(analyze(report())["live_trading_approved"])

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
            self.assertEqual(result["strategies"][0]["validation_folds"], 4)

if __name__ == "__main__":
    unittest.main()
