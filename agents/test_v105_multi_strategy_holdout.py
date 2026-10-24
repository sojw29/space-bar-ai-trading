import csv
import tempfile
import unittest
from pathlib import Path
from multi_strategy_holdout_v105 import run, _metrics, STRATEGIES

class MultiStrategyHoldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "history.csv"

    def write(self, n=400):
        with self.source.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for i in range(n):
                price = 100 + 0.03*i + (3 if (i//20)%2 else -3)
                writer.writerow([1700000000000+i*300000, price, price+1,
                                 price-1, price, 150 if i%17==0 else 80])

    def test_three_strategies_have_distinct_results(self):
        self.write()
        result = run(self.source)
        self.assertEqual(result["strategy_count"], 3)
        self.assertEqual({x["strategy"] for x in result["strategies"]}, set(STRATEGIES))
        self.assertEqual(result["split"]["train_rows"], 280)
        self.assertEqual(result["split"]["validation_rows"], 120)
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["validated_edge"])

    def test_deterministic(self):
        self.write()
        self.assertEqual(run(self.source), run(self.source))

    def test_insufficient_holdout_rejected(self):
        self.write(120)
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_ROWS"):
            run(self.source)

    def test_unknown_strategy_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_STRATEGY"):
            _metrics([{}]*100, "LIVE_ORDER")

    def test_unsorted_input_rejected(self):
        self.write()
        lines = self.source.read_text().splitlines()
        lines[3], lines[4] = lines[4], lines[3]
        self.source.write_text("\n".join(lines)+"\n")
        with self.assertRaisesRegex(ValueError, "NON_MONOTONIC"):
            run(self.source)

if __name__ == "__main__":
    unittest.main()
