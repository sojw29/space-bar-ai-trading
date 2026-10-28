"""V197 strategy scorecard: descriptive, deterministic and fail-closed."""
import unittest
from strategy_comparison_scorecard_v197 import build_scorecard


def example():
    return {"version": "V105.0", "research_only": True,
            "orders_enabled": False, "live_trading_approved": False,
            "strategies": [
                {"strategy": name, "validation": {"trades": 20, "win_rate": 55.0,
                  "return": -2.0, "profit_factor": 0.9, "max_drawdown": 8.0}}
                for name in ("ZETA", "ALPHA")],
            "evidence_assessments": [
                {"status": "INSUFFICIENT_EVIDENCE", "evidence_sufficient": False,
                 "failures": ["insufficient_holdout_trades"],
                 "orders_allowed": False, "live_trading_approved": False}
                for _ in range(2)]}


class ScorecardTests(unittest.TestCase):
    def test_side_by_side_no_ranking_or_approval(self):
        result = build_scorecard(example())
        self.assertEqual([row["strategy"] for row in result["rows"]], ["ALPHA", "ZETA"])
        self.assertFalse(result["ranking_enabled"])
        self.assertFalse(result["strategy_selection_enabled"])
        self.assertFalse(result["orders_allowed"])
        self.assertFalse(result["live_trading_approved"])

    def test_mismatched_assessments_block(self):
        report = example()
        report["evidence_assessments"].pop()
        with self.assertRaises(ValueError):
            build_scorecard(report)

    def test_nonfinite_metric_blocks(self):
        report = example()
        report["strategies"][0]["validation"]["return"] = float("nan")
        with self.assertRaises(ValueError):
            build_scorecard(report)

    def test_unsafe_assessment_blocks(self):
        report = example()
        report["evidence_assessments"][0]["orders_allowed"] = True
        with self.assertRaises(ValueError):
            build_scorecard(report)

    def test_duplicate_strategy_blocks(self):
        report = example()
        report["strategies"][1]["strategy"] = "ZETA"
        with self.assertRaises(ValueError):
            build_scorecard(report)

    def test_unsafe_report_blocks(self):
        report = example()
        report["orders_enabled"] = True
        with self.assertRaisesRegex(ValueError, "UNSAFE_V105_REPORT"):
            build_scorecard(report)

    def test_contradictory_evidence_blocks(self):
        report = example()
        report["evidence_assessments"][0]["status"] = "EVIDENCE_REVIEWABLE"
        with self.assertRaisesRegex(ValueError, "INCONSISTENT_EVIDENCE_STATUS"):
            build_scorecard(report)
        report = example()
        report["evidence_assessments"][0]["failures"] = []
        with self.assertRaisesRegex(ValueError, "INCONSISTENT_EVIDENCE_STATUS"):
            build_scorecard(report)

    def test_invalid_evidence_failures_blocks(self):
        report = example()
        report["evidence_assessments"][0]["failures"] = "insufficient_holdout_trades"
        with self.assertRaisesRegex(ValueError, "INVALID_EVIDENCE_SCHEMA"):
            build_scorecard(report)

    def test_reviewable_evidence_is_not_trade_approval(self):
        report = example()
        for assessment in report["evidence_assessments"]:
            assessment["status"] = "EVIDENCE_REVIEWABLE"
            assessment["evidence_sufficient"] = True
            assessment["failures"] = []
        result = build_scorecard(report)
        self.assertEqual(result["rows"][0]["evidence_status"], "EVIDENCE_REVIEWABLE")
        self.assertFalse(result["orders_allowed"])
        self.assertFalse(result["live_trading_approved"])

    def test_invalid_metric_range_blocks(self):
        report = example()
        report["strategies"][0]["validation"]["return"] = -101.0
        with self.assertRaisesRegex(ValueError, "INVALID_METRIC_RANGE"):
            build_scorecard(report)

    def test_output_does_not_alias_input_failures(self):
        report = example()
        result = build_scorecard(report)
        report["evidence_assessments"][1]["failures"].append("later_mutation")
        self.assertEqual(result["rows"][0]["evidence_failures"], ["insufficient_holdout_trades"])


if __name__ == "__main__":
    unittest.main()
