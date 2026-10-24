import csv
import tempfile
import unittest
from pathlib import Path
from market_regime_v107 import run, classify, summarize

class MarketRegimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"history.csv"

    def rows(self, n=400):
        return [{"timestamp": str(1700000000000+i*300000),
                 "open": str(100+i*0.01), "high": str(101+i*0.01),
                 "low": str(99+i*0.01), "close": str(100+i*0.01),
                 "volume": "100"} for i in range(n)]

    def write(self, rows):
        with self.path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp","open","high","low","close","volume"])
            writer.writeheader()
            writer.writerows(rows)

    def test_regime_pipeline(self):
        self.write(self.rows())
        result = run(self.path)
        self.assertEqual(result["train"]["count"], 260)
        self.assertEqual(result["validation"]["count"], 100)
        self.assertFalse(result["live_trading_approved"])

    def test_future_changes_do_not_change_past_labels(self):
        rows = self.rows()
        before = classify(rows)
        rows[-1]["close"] = "500"
        after = classify(rows)
        self.assertEqual(before[:-1], after[:-1])

    def test_all_regimes_counted(self):
        labels = classify(self.rows())
        self.assertEqual(sum(summarize(labels)["regime_counts"].values()), len(labels))

    def test_invalid_close_rejected(self):
        rows = self.rows()
        rows[50]["close"] = "nan"
        with self.assertRaisesRegex(ValueError, "INVALID_CLOSE"):
            classify(rows)

    def test_short_data_rejected(self):
        self.write(self.rows(100))
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_ROWS"):
            run(self.path)

if __name__ == "__main__":
    unittest.main()
