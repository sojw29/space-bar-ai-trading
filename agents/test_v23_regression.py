"""Offline regression checks for V18-V22. No exchange access required."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tester_v18 as v18
import tester_v19 as v19
import tester_v21 as v21
import tester_v22 as v22


class RegressionTests(unittest.TestCase):
    def test_null_profit_factor(self):
        self.assertIsNone(v18.number({"profit_factor": "None"}, "profit_factor"))
        self.assertIsNone(v18.number({"profit_factor": ""}, "profit_factor"))
        self.assertEqual(v18.number({"profit_factor": "1.25"}, "profit_factor"), 1.25)
        self.assertIsNone(v19.parse_float(None))

    def test_v21_end_of_data_not_finalized(self):
        base = dict(candidate="A", scenario="BASE", side="LONG",
                    entry_time="100", entry_price="50", exit_time="200",
                    exit_price="51", net_pnl_usd="1", reason="TP")
        provisional = dict(base, entry_time="300", reason="END")
        result = v21.reconcile(None, [base, provisional])
        self.assertEqual(result["current_finalized_trades"], 1)
        self.assertIsNone(result["new_finalized_trades"])
        self.assertEqual(result["status"], "BASELINE_ONLY")

    def test_v21_detects_revisions_and_missing(self):
        base = dict(candidate="A", scenario="BASE", side="LONG",
                    entry_time="100", entry_price="50", exit_time="200",
                    exit_price="51", net_pnl_usd="1", reason="TP")
        changed = dict(base, exit_price="49", net_pnl_usd="-1", reason="SL")
        new = dict(base, entry_time="400")
        result = v21.reconcile([base], [changed, new])
        self.assertEqual(result["new_finalized_trades"], 1)
        self.assertEqual(len(result["revised_previous_trades"]), 1)
        self.assertEqual(result["status"], "RECONCILIATION_WARNING")
        self.assertEqual(len(v21.reconcile([base], [new])["missing_previous_trades"]), 1)

    def test_v19_quality_empty_sample(self):
        self.assertIsNone(v19.parse_float("nan"))
        self.assertIsNone(v19.parse_float("null"))

    def test_v21_duplicate_trade_identity(self):
        base = dict(candidate="A", scenario="BASE", side="LONG",
                    entry_time="100", entry_price="50", exit_time="200",
                    exit_price="51", net_pnl_usd="1", reason="TP")
        result = v21.reconcile(None, [base, base])
        self.assertEqual(len(result["duplicate_current_ids"]), 1)

    def test_v22_candle_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candles.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp"])
                writer.writeheader()
                for ts in [300, 600, 1200, 1200, 1500]:
                    writer.writerow({"timestamp": ts})
            result = v22.inspect_candles(path, 900)
            self.assertEqual(result["forward_candle_count"], 3)
            self.assertEqual(result["nonconsecutive_intervals"], 1)
            self.assertEqual(result["duplicate_or_unsorted_timestamps"], 1)
            self.assertEqual(result["first_forward_candle_utc"], v22.v17.utc(1200))
            self.assertEqual(result["last_forward_candle_utc"], v22.v17.utc(1500))


if __name__ == "__main__":
    unittest.main(verbosity=2)
