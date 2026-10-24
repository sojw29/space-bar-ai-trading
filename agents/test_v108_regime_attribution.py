import csv
import tempfile
import unittest
from pathlib import Path
from regime_attribution_v108 import run, attribute, REGIMES
from cost_sensitivity_v106 import SCENARIOS

class RegimeAttributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"history.csv"

    def make_rows(self, n=400):
        return [{"timestamp": str(1700000000000+i*300000),
                 "open": str(100+0.02*i+(4 if (i//20)%2 else -4)),
                 "high": str(101+0.02*i+(4 if (i//20)%2 else -4)),
                 "low": str(99+0.02*i+(4 if (i//20)%2 else -4)),
                 "close": str(100+0.02*i+(4 if (i//20)%2 else -4)),
                 "volume": str(200 if i%17==0 else 100)} for i in range(n)]

    def write(self, rows):
        with self.path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp","open","high","low","close","volume"])
            writer.writeheader()
            writer.writerows(rows)

    def test_pipeline(self):
        self.write(self.make_rows())
        result = run(self.path)
        self.assertEqual(len(result["results"]), 3)
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["validated_edge"])

    def test_trade_count_and_pnl_reconcile(self):
        rows = self.make_rows()
        for strategy in ("EMA_CROSS", "EMA_PULLBACK", "VOLUME_BREAKOUT"):
            report = attribute(rows, strategy, SCENARIOS["moderate"])
            by_regime = report["by_entry_regime"]
            self.assertEqual(sum(v["closed_trades"] for v in by_regime.values()),
                             report["closed_trades"])
            self.assertAlmostEqual(sum(v["net_pnl"] for v in by_regime.values()),
                                   report["attribution_total_net_pnl"], places=4)
            self.assertEqual(set(by_regime), set(REGIMES))

    def test_deterministic(self):
        self.write(self.make_rows())
        self.assertEqual(run(self.path), run(self.path))

    def test_small_data_rejected(self):
        self.write(self.make_rows(120))
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_ROWS"):
            run(self.path)

    def test_unknown_strategy_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_STRATEGY"):
            attribute(self.make_rows(), "LIVE", SCENARIOS["moderate"])

if __name__ == "__main__":
    unittest.main()
