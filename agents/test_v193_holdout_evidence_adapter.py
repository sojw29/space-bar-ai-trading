"""V193 legacy holdout adapter never silently approves incomplete costs."""
import unittest
from holdout_evidence_adapter_v193 import assess_legacy_holdout


def sample():
    return {
        "version": "V104.0",
        "research_only": True,
        "orders_enabled": False,
        "fee_rate_per_side": 0.00055,
        "comparison": {
            "independent_holdout": True,
            "strategy_frozen_before_validation": True,
            "validation": {"trades": 150, "return": 5.0, "max_drawdown": 4.0, "profit_factor": 1.5},
        },
    }


class LegacyAdapterTests(unittest.TestCase):
    def test_legacy_positive_metrics_do_not_override_missing_slippage(self):
        result = assess_legacy_holdout(sample())
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("missing_execution_costs", result["failures"])
        self.assertIn("costs_not_included", result["failures"])
        self.assertFalse(result["orders_allowed"])
        self.assertFalse(result["live_trading_approved"])

    def test_missing_report_fails_closed(self):
        for value in (None, [], {}, {"comparison": []}):
            with self.subTest(value=value):
                self.assertFalse(assess_legacy_holdout(value)["evidence_sufficient"])

    def test_small_holdout_adds_sample_failure(self):
        report = sample()
        report["comparison"]["validation"]["trades"] = 8
        self.assertIn("insufficient_holdout_trades", assess_legacy_holdout(report)["failures"])

    def test_missing_attestation_adds_failure(self):
        report = sample()
        report["comparison"]["independent_holdout"] = False
        self.assertIn("holdout_not_verified", assess_legacy_holdout(report)["failures"])


if __name__ == "__main__":
    unittest.main()
