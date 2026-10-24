import csv
import tempfile
import unittest
from pathlib import Path
from cost_sensitivity_v106 import run, backtest, SCENARIOS

class CostSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)/"history.csv"

    def write(self, n=400):
        with self.source.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for i in range(n):
                price = 100+0.02*i+(4 if (i//20)%2 else -4)
                writer.writerow([1700000000000+i*300000,price,price+1,price-1,price,
                                 200 if i%17==0 else 100])

    def test_pipeline_three_strategies_three_scenarios(self):
        self.write()
        report = run(self.source)
        self.assertEqual(len(report["results"]), 9)
        self.assertEqual(report["scenario_count"], 3)
        self.assertFalse(report["live_trading_approved"])
        self.assertFalse(report["validated_edge"])

    def test_stress_not_better_than_baseline_on_same_trades(self):
        self.write()
        with self.source.open(newline="") as f:
            rows = list(csv.DictReader(f))
        for strategy in ("EMA_CROSS", "EMA_PULLBACK", "VOLUME_BREAKOUT"):
            base = backtest(rows, strategy, SCENARIOS["baseline"])
            stress = backtest(rows, strategy, SCENARIOS["stress"])
            self.assertLessEqual(stress["return"], base["return"]+1e-6)

    def test_deterministic(self):
        self.write()
        self.assertEqual(run(self.source), run(self.source))

    def test_invalid_cost_rejected(self):
        self.write()
        with self.source.open(newline="") as f:
            rows = list(csv.DictReader(f))
        costs = dict(SCENARIOS["baseline"], fee_bps=-1)
        with self.assertRaisesRegex(ValueError, "INVALID_COST_RATE"):
            backtest(rows, "EMA_CROSS", costs)

    def test_small_data_rejected(self):
        self.write(120)
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_ROWS"):
            run(self.source)

if __name__ == "__main__":
    unittest.main()
