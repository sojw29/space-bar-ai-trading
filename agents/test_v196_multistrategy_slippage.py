"""V196: fixed adverse slippage must not improve V105 backtest returns."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import multi_strategy_holdout_v105 as multi


class MultiStrategySlippageTests(unittest.TestCase):
    def test_all_strategies_slippage_is_adverse(self):
        rows = []
        for i in range(500):
            price = 100 + i * 0.01 + (5 if (i // 20) % 2 else -5)
            rows.append({"open": str(price), "close": str(price),
                         "high": str(price + 1), "low": str(price - 1),
                         "volume": str(200 if i % 7 == 0 else 100)})
        for strategy in multi.STRATEGIES:
            with self.subTest(strategy=strategy):
                with patch.object(multi, "SLIPPAGE_RATE", 0):
                    zero = multi._metrics(rows, strategy)
                with patch.object(multi, "SLIPPAGE_RATE", 0.0002):
                    adverse = multi._metrics(rows, strategy)
                self.assertEqual(zero["trades"], adverse["trades"])
                self.assertLessEqual(adverse["return"], zero["return"])

    def test_cost_model_is_explicit_and_never_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "BTC_5m.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
                writer.writeheader()
                for i in range(600):
                    price = 100 + i * 0.01 + (5 if (i // 20) % 2 else -5)
                    writer.writerow({"timestamp": 1700000000000 + i * 300000,
                                     "open": price, "high": price + 1, "low": price - 1,
                                     "close": price, "volume": 100})
            result = multi.run(path)
            self.assertEqual(result["slippage_rate_per_side"], 0.0002)
            self.assertTrue(result["holdout_includes_fees_and_slippage"])
            self.assertEqual(len(result["evidence_assessments"]), 3)
            for assessment in result["evidence_assessments"]:
                self.assertNotIn("missing_execution_costs", assessment["failures"])
                self.assertNotIn("costs_not_included", assessment["failures"])
                self.assertFalse(assessment["orders_allowed"])
                self.assertFalse(assessment["live_trading_approved"])
            self.assertFalse(result["orders_enabled"])


if __name__ == "__main__":
    unittest.main()
