"""V194: real V104/V105 pipeline output includes fail-closed evidence assessments."""
import csv
import tempfile
import unittest
from pathlib import Path
from ema_holdout_pipeline_v104 import run as ema_run
from multi_strategy_holdout_v105 import run as multi_run


class HoldoutPipelineEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name) / "BTC_5m.csv"
        with cls.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
            writer.writeheader()
            for i in range(600):
                price = 100 + i * 0.02 + (i % 30 - 15) * 0.15
                writer.writerow({"timestamp": 1700000000000 + i * 300000,
                                 "open": price, "high": price + 1, "low": price - 1,
                                 "close": price + 0.1, "volume": 100 + i % 20})

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def assert_insufficient(self, assessment):
        self.assertEqual(assessment["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(assessment["evidence_sufficient"])
        self.assertIn("missing_execution_costs", assessment["failures"])
        self.assertIn("costs_not_included", assessment["failures"])
        self.assertFalse(assessment["orders_allowed"])
        self.assertFalse(assessment["live_trading_approved"])

    def test_v104_emits_assessment(self):
        report = ema_run(self.path)
        assessment = report["evidence_assessment"]
        self.assertEqual(assessment["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("insufficient_holdout_trades", assessment["failures"])
        self.assertNotIn("missing_execution_costs", assessment["failures"])
        self.assertNotIn("costs_not_included", assessment["failures"])
        self.assertFalse(assessment["orders_allowed"])
        self.assertFalse(report["orders_enabled"])

    def test_v105_emits_assessment_per_strategy(self):
        report = multi_run(self.path)
        self.assertEqual(len(report["evidence_assessments"]), len(report["strategies"]))
        self.assertEqual(len(report["evidence_assessments"]), 3)
        for assessment in report["evidence_assessments"]:
            self.assert_insufficient(assessment)
        self.assertFalse(report["orders_enabled"])


if __name__ == "__main__":
    unittest.main()
