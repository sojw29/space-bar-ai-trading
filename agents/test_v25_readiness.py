"""Offline tests for conservative V25 research readiness."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tester_v25 as v25


class V25Tests(unittest.TestCase):
    def test_insufficient_and_missing_snapshots(self):
        report = {"warnings": [], "candidates": [{"candidate": "A",
            "base_trades": 2, "stress_trades": 2, "severe_trades": 2,
            "base_return_pct": 1, "stress_return_pct": 0, "severe_return_pct": -1,
            "base_profit_factor": 1.2, "stress_profit_factor": 1.1,
            "severe_profit_factor": 0.9, "cost_return_monotonic": True}]}
        result = v25.evaluate(report, None, None)
        row = result["candidates"][0]
        self.assertFalse(row["sample_minimum_met"])
        self.assertIn("NO_PRIOR_EVIDENCE_SNAPSHOT", row["reasons"])
        self.assertIn("INSUFFICIENT_BASE_TRADES", row["reasons"])
        self.assertFalse(row["live_trading_approved"])

    def test_even_good_research_not_live_approved(self):
        row = {"candidate": "A", "cost_return_monotonic": True}
        for scenario in ("base", "stress", "severe"):
            row.update({scenario + "_trades": 40, scenario + "_return_pct": 1.0,
                        scenario + "_profit_factor": 1.5})
        result = v25.evaluate({"warnings": [], "candidates": [row]},
            {"integrity_pass": True, "prior_evidence_available": True},
            {"previous_snapshot_available": True, "status": "OBSERVATION_ONLY"})
        self.assertEqual(result["candidates"][0]["observation_quality_status"], "PRELIMINARY_RESEARCH_ONLY")
        self.assertFalse(result["independent_oos_verified"])
        self.assertFalse(result["live_trading_approved"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
