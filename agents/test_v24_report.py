"""V24 report contract checks, no network or historical data needed."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tester_v24 as v24


class V24Tests(unittest.TestCase):
    def test_missing_and_undefined_metrics(self):
        rows = [{"candidate": "A", "scenario": "BASE", "return_pct": "None", "profit_factor": ""}]
        report = v24.summarize(rows)
        self.assertIn("MISSING_SCENARIOS", report["warnings"])
        self.assertIsNone(report["candidates"][0]["base_return_pct"])
        self.assertIn("N/A", v24.render_markdown(report))
        self.assertFalse(report["live_trading_approved"])

    def test_cost_monotonic(self):
        rows = [
            {"candidate": "A", "scenario": scenario, "return_pct": value}
            for scenario, value in [("BASE", "2"), ("STRESS", "1"), ("SEVERE", "-1")]
        ]
        self.assertTrue(v24.summarize(rows)["candidates"][0]["cost_return_monotonic"])
        rows[-1]["return_pct"] = "3"
        report = v24.summarize(rows)
        self.assertFalse(report["candidates"][0]["cost_return_monotonic"])
        self.assertIn("NONMONOTONIC_COST_RETURNS_A", report["warnings"])

    def test_duplicate_scenario_fails(self):
        rows = [{"candidate": "A", "scenario": "BASE"}] * 2
        with self.assertRaises(ValueError):
            v24.summarize(rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)
