import csv
import tempfile
import unittest
from pathlib import Path
from ema_holdout_pipeline_v104 import run, backtest

class EMAHoldoutPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"history.csv"

    def make_data(self, n=300):
        with self.path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp","open","high","low","close","volume"])
            for i in range(n):
                price = 100 + 0.02*i + 3*((i//25)%2)
                writer.writerow([1700000000000+i*300000,price,price+1,
                                 price-1,price,100])

    def test_pipeline_produces_real_comparison(self):
        self.make_data()
        result = run(self.path)
        self.assertEqual(result["split"]["train_rows"], 210)
        self.assertEqual(result["split"]["validation_rows"], 90)
        self.assertEqual(result["comparison"]["status"], "REVIEW_REQUIRED")
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["orders_enabled"])

    def test_short_data_rejected(self):
        self.make_data(100)
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_ROWS"):
            run(self.path)

    def test_unsorted_data_rejected(self):
        self.make_data()
        rows = self.path.read_text().splitlines()
        rows[2], rows[3] = rows[3], rows[2]
        self.path.write_text("\n".join(rows)+"\n")
        with self.assertRaisesRegex(ValueError, "NON_MONOTONIC"):
            run(self.path)

    def test_backtest_deterministic(self):
        self.make_data()
        first = backtest(self.path)
        second = backtest(self.path)
        self.assertEqual(first, second)
        self.assertGreaterEqual(first["trades"], 0)

if __name__ == "__main__":
    unittest.main()
