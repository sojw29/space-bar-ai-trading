"""V192 offline backtest evidence gate regression tests."""
import copy
import unittest
from backtest_evidence_gate_v192 import evaluate_backtest_evidence


def example():
    return {
        "mode": "historical_offline_backtest",
        "holdout_is_out_of_sample": True,
        "strategy_parameters_frozen_before_holdout": True,
        "research_only": True,
        "orders_enabled": False,
        "fee_pct_per_side": 0.055,
        "slippage_pct_per_side": 0.02,
        "holdout_includes_fees_and_slippage": True,
        "holdout": {"trades": 120, "net_return_pct": -4.0, "max_drawdown_pct": 12.0, "profit_factor": 0.8},
    }


class EvidenceGateTests(unittest.TestCase):
    def test_complete_negative_results_are_reviewable_not_approved(self):
        result = evaluate_backtest_evidence(example())
        self.assertEqual(result["status"], "EVIDENCE_REVIEWABLE")
        self.assertFalse(result["orders_allowed"])
        self.assertFalse(result["live_trading_approved"])

    def test_small_holdout_is_insufficient(self):
        report = example()
        report["holdout"]["trades"] = 8
        self.assertIn("insufficient_holdout_trades", evaluate_backtest_evidence(report)["failures"])

    def test_invalid_minimum_override_never_bypasses_100_trade_floor(self):
        report = example()
        report["holdout"]["trades"] = 1
        for minimum in (0, -1, True, 5.0, "100", None):
            with self.subTest(minimum=minimum):
                result = evaluate_backtest_evidence(report, min_holdout_trades=minimum)
                self.assertFalse(result["evidence_sufficient"])
                self.assertIn("invalid_min_holdout_trades", result["failures"])
                self.assertIn("insufficient_holdout_trades", result["failures"])
                self.assertFalse(result["orders_allowed"])

    def test_negative_profit_factor_is_invalid(self):
        report = example()
        report["holdout"]["profit_factor"] = -0.1
        result = evaluate_backtest_evidence(report)
        self.assertFalse(result["evidence_sufficient"])
        self.assertIn("invalid_profit_factor_range", result["failures"])

    def test_missing_costs_or_cost_inclusion(self):
        for key, value in (("fee_pct_per_side", None), ("slippage_pct_per_side", -1), ("holdout_includes_fees_and_slippage", False)):
            with self.subTest(key=key):
                report = example()
                report[key] = value
                self.assertFalse(evaluate_backtest_evidence(report)["evidence_sufficient"])

    def test_nonfinite_metrics_block(self):
        for key, value in (("net_return_pct", float("nan")), ("max_drawdown_pct", float("inf")), ("profit_factor", None)):
            with self.subTest(key=key):
                report = example()
                report["holdout"][key] = value
                self.assertFalse(evaluate_backtest_evidence(report)["evidence_sufficient"])

    def test_in_sample_or_tuned_holdout_blocks(self):
        for key in ("holdout_is_out_of_sample", "strategy_parameters_frozen_before_holdout"):
            report = example()
            report[key] = False
            self.assertFalse(evaluate_backtest_evidence(report)["evidence_sufficient"])

    def test_unsafe_or_malformed_blocks(self):
        for report in (None, [], {}, {"orders_enabled": True}):
            with self.subTest(report=report):
                result = evaluate_backtest_evidence(report)
                self.assertFalse(result["evidence_sufficient"])
                self.assertFalse(result["orders_allowed"])

    def test_drawdown_range_and_boolean_metrics(self):
        for value in (-1, 101, True):
            report = example()
            report["holdout"]["max_drawdown_pct"] = value
            self.assertFalse(evaluate_backtest_evidence(report)["evidence_sufficient"])


if __name__ == "__main__":
    unittest.main()
