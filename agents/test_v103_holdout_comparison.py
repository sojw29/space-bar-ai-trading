import unittest
from holdout_comparison_v103 import compare

def example():
    return {
        "strategy": "EMA_CROSS", "symbol": "BTC", "timeframe": "5m",
        "chronological": True, "independent_holdout": True,
        "strategy_frozen_before_validation": True,
        "train": {"trades": 100, "win_rate": 60.0, "return": 8.0,
                  "profit_factor": 1.8, "max_drawdown": 4.0},
        "validation": {"trades": 50, "win_rate": 40.0, "return": -2.0,
                       "profit_factor": 0.8, "max_drawdown": 9.0},
    }

class HoldoutComparisonTests(unittest.TestCase):
    def test_degradation_flag_and_deltas(self):
        result = compare(example())
        self.assertTrue(result["possible_generalization_degradation"])
        self.assertEqual(result["delta_validation_minus_train"]["return_pct_points"], -10.0)
        self.assertEqual(result["delta_validation_minus_train"]["win_rate_pct_points"], -20.0)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertFalse(result["strategy_profitable_verified"])

    def test_good_validation_still_not_approved(self):
        data = example()
        data["validation"]["return"] = 9.0
        data["validation"]["profit_factor"] = 2.0
        result = compare(data)
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["independently_verified"])

    def test_low_sample_blocked(self):
        data = example()
        data["validation"]["trades"] = 5
        result = compare(data)
        self.assertFalse(result["sample_sufficient"])
        self.assertEqual(result["checks"][0]["status"], "BLOCKED")

    def test_no_independent_holdout_attestation(self):
        data = example()
        data["independent_holdout"] = False
        result = compare(data)
        self.assertFalse(result["holdout_attested"])
        self.assertEqual(result["checks"][1]["status"], "BLOCKED")

    def test_nonfinite_rejected(self):
        data = example()
        data["train"]["return"] = float("nan")
        with self.assertRaises(ValueError):
            compare(data)

    def test_invalid_win_rate_rejected(self):
        data = example()
        data["validation"]["win_rate"] = 110
        with self.assertRaises(ValueError):
            compare(data)

    def test_missing_schema_field_rejected(self):
        data = example()
        del data["strategy"]
        with self.assertRaises(ValueError):
            compare(data)

    def test_minimum_trade_count_cannot_be_lowered(self):
        with self.assertRaises(ValueError):
            compare(example(), min_trades=1)

if __name__ == "__main__":
    unittest.main()
