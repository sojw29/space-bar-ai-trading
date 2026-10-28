"""V195 regression: adverse slippage changes hypothetical EMA fills."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ema_holdout_pipeline_v104 as ema


class EMASlippageTests(unittest.TestCase):
    def test_adverse_slippage_never_improves_fixed_signal_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "BTC_5m.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
                writer.writeheader()
                for i in range(500):
                    price = 100 + 5 * ((i // 25) % 2) + i * 0.01
                    writer.writerow({"timestamp": 1700000000000 + i * 300000,
                                     "open": price, "high": price + 1, "low": price - 1,
                                     "close": price, "volume": 100})
            with patch.object(ema, "SLIPPAGE_RATE", 0.0):
                no_slippage = ema.backtest(path)
            with patch.object(ema, "SLIPPAGE_RATE", 0.0002):
                adverse = ema.backtest(path)
            self.assertGreater(no_slippage["trades"], 0)
            self.assertEqual(no_slippage["trades"], adverse["trades"])
            self.assertLessEqual(adverse["return"], no_slippage["return"])

    def test_pipeline_attests_fixed_costs_without_live_approval(self):
        self.assertEqual(ema.SLIPPAGE_RATE, 0.0002)
        from holdout_evidence_adapter_v193 import assess_legacy_holdout
        report = {
            "version": "V104.0", "research_only": True, "orders_enabled": False,
            "fee_rate_per_side": ema.FEE_RATE,
            "slippage_rate_per_side": ema.SLIPPAGE_RATE,
            "holdout_includes_fees_and_slippage": True,
            "comparison": {"independent_holdout": True, "strategy_frozen_before_validation": True,
                           "validation": {"trades": 2, "return": -1, "max_drawdown": 5, "profit_factor": 0.5}},
        }
        result = assess_legacy_holdout(report)
        self.assertNotIn("missing_execution_costs", result["failures"])
        self.assertIn("insufficient_holdout_trades", result["failures"])
        self.assertFalse(result["orders_allowed"])
        self.assertFalse(result["live_trading_approved"])


if __name__ == "__main__":
    unittest.main()
