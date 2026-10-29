"""V198 actual V105 holdout pipeline includes descriptive scorecard."""
import csv
import tempfile
import unittest
from pathlib import Path

from multi_strategy_holdout_v105 import STRATEGIES, run


class PipelineScorecardTests(unittest.TestCase):
    def test_scorecard_matches_holdout_metrics_and_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
                writer.writeheader()
                for i in range(600):
                    price = 100 + i * 0.02 + (5 if (i // 25) % 2 else -5)
                    writer.writerow({"timestamp": 1700000000000 + i * 300000,
                                     "open": price, "high": price + 1, "low": price - 1,
                                     "close": price, "volume": 150 if i % 17 == 0 else 80})
            result = run(path)
            scorecard = result["strategy_scorecard"]
            self.assertEqual(scorecard["status"], "RESEARCH_COMPARISON_ONLY")
            self.assertEqual({row["strategy"] for row in scorecard["rows"]}, set(STRATEGIES))
            self.assertFalse(scorecard["ranking_enabled"])
            self.assertFalse(scorecard["strategy_selection_enabled"])
            self.assertFalse(scorecard["orders_allowed"])
            self.assertFalse(scorecard["live_trading_approved"])
            originals = {entry["strategy"]: entry["validation"] for entry in result["strategies"]}
            for row in scorecard["rows"]:
                metrics = originals[row["strategy"]]
                self.assertEqual(row["holdout_trades"], metrics["trades"])
                self.assertEqual(row["holdout_net_return_pct"], metrics["return"])
                self.assertEqual(row["holdout_profit_factor"], metrics["profit_factor"])
                self.assertEqual(row["holdout_max_drawdown_pct"], metrics["max_drawdown"])
            self.assertFalse(result["orders_enabled"])


if __name__ == "__main__":
    unittest.main()
