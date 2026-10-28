"""V197 strategy scorecard: descriptive, deterministic and fail-closed."""
import unittest
from strategy_comparison_scorecard_v197 import build_scorecard


def example():
    return {"version": "V105.0",
            "strategies": [
                {"strategy": name, "validation": {"trades": 20, "win_rate": 55.0,
                  "return": -2.0, "profit_factor": 0.9, "max_drawdown": 8.0}}
                for name in ("ZETA", "ALPHA")],
            "evidence_assessments": [
                {"status": "INSUFFICIENT_EVIDENCE", "failures": ["insufficient_holdout_trades"],
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


if __name__ == "__main__":
    unittest.main()
