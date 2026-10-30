"""Offline regression checks for V18-V22. No exchange access required."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tester_v17 as v17
import tester_v18 as v18
import tester_v19 as v19
import tester_v21 as v21
import tester_v22 as v22


class RegressionTests(unittest.TestCase):
    def test_v17_empty_forward_window_label(self):
        before = v17.CUTOFF - 300
        label = v17.forward_window_label([{"timestamp": before}])
        self.assertIn("NO_FORWARD_CANDLES", label)
        self.assertIn(v17.utc(before), label)
        self.assertIn(v17.utc(v17.CUTOFF), label)
        after = v17.CUTOFF + 300
        label = v17.forward_window_label([{"timestamp": after}])
        self.assertNotIn("NO_FORWARD_CANDLES", label)
        self.assertIn(v17.utc(after), label)


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

    def test_artifact_layout_resolution(self):
        # upload-artifact may strip the shared reports/ parent.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            v21_root = root / "previous_v21"
            v22_root = root / "previous_v22"
            (v21_root / "v17").mkdir(parents=True)
            (v22_root / "v22").mkdir(parents=True)
            (v21_root / "v17" / "trades.csv").write_text("candidate,scenario\\n")
            (v22_root / "v22" / "evidence.json").write_text("{}")
            with patch.object(v21, "PREVIOUS", v21_root / "trades.csv"), \
                 patch.object(v22, "PREVIOUS", v22_root):
                self.assertEqual(v21.previous_trades_path(),
                                 v21_root / "v17" / "trades.csv")
                self.assertEqual(v22.previous_evidence_path(),
                                 v22_root / "v22" / "evidence.json")
                (v21_root / "reports" / "v17").mkdir(parents=True)
                (v22_root / "reports" / "v22").mkdir(parents=True)
                (v21_root / "v17" / "trades.csv").unlink()
                (v22_root / "v22" / "evidence.json").unlink()
                (v21_root / "reports" / "v17" / "trades.csv").write_text("candidate,scenario\\n")
                (v22_root / "reports" / "v22" / "evidence.json").write_text("{}")
                self.assertEqual(v21.previous_trades_path(),
                                 v21_root / "reports" / "v17" / "trades.csv")
                self.assertEqual(v22.previous_evidence_path(),
                                 v22_root / "reports" / "v22" / "evidence.json")

    def test_v21_finalized_counts_exclude_end(self):
        rows = [
            dict(candidate="A", scenario="BASE", side="LONG",
                 entry_time="100", entry_price="50", reason="TP"),
            dict(candidate="A", scenario="BASE", side="LONG",
                 entry_time="200", entry_price="50", reason="END"),
            dict(candidate="A", scenario="STRESS", side="LONG",
                 entry_time="300", entry_price="50", reason="SL"),
        ]
        counts = v21.finalized_by_scenario(v21.closed(rows)[0])
        self.assertEqual(counts, {"A": {"BASE": 1, "STRESS": 1}})

    def test_v22_integrity_pass_without_forward_data_is_not_evidence(self):
        candles = {"forward_candle_count": 0, "nonconsecutive_intervals": 0}
        self.assertEqual(v22.forward_evidence_status(candles, []), "NO_FORWARD_CANDLES")
        self.assertEqual(v22.forward_evidence_status(candles, ["CUTOFF_DRIFT"]), "INTEGRITY_FAILURE")
        candles["forward_candle_count"] = 10
        candles["nonconsecutive_intervals"] = 1
        self.assertEqual(v22.forward_evidence_status(candles, []), "CANDLE_GAPS_REQUIRE_REVIEW")
        candles["nonconsecutive_intervals"] = 0
        self.assertEqual(v22.forward_evidence_status(candles, [], baseline_available=True), "FORWARD_CANDLES_PRESENT_UNVERIFIED")

    def test_v22_unchanged_forward_snapshot_not_usable(self):
        candles = {"forward_candle_count": 10, "nonconsecutive_intervals": 0}
        self.assertEqual(
            v22.forward_evidence_status(candles, [], ["NO_NEW_FORWARD_CANDLES"]),
            "NO_NEW_FORWARD_CANDLES",
        )
        self.assertNotEqual(
            v22.forward_evidence_status(candles, [], ["NO_NEW_FORWARD_CANDLES"]),
            "FORWARD_CANDLES_PRESENT_UNVERIFIED",
        )
        self.assertEqual(
            v22.forward_evidence_status(candles, [], [], baseline_available=True),
            "FORWARD_CANDLES_PRESENT_UNVERIFIED",
        )
        self.assertEqual(
            v22.forward_evidence_status(candles, ["FORWARD_DATA_REGRESSION"], ["NO_NEW_FORWARD_CANDLES"]),
            "INTEGRITY_FAILURE",
        )

    def test_v22_forward_research_usability_respects_warnings(self):
        candles = {"forward_candle_count": 10, "nonconsecutive_intervals": 0}
        self.assertFalse(v22.forward_evidence_usable_for_research(
            candles, [], ["NO_NEW_FORWARD_CANDLES"]))
        self.assertFalse(v22.forward_evidence_usable_for_research(
            candles, ["CUTOFF_DRIFT"], []))
        self.assertFalse(v22.forward_evidence_usable_for_research(
            {"forward_candle_count": 0, "nonconsecutive_intervals": 0}, [], []))
        self.assertFalse(v22.forward_evidence_usable_for_research(
            {"forward_candle_count": 10, "nonconsecutive_intervals": 1}, [], []))
        self.assertTrue(v22.forward_evidence_usable_for_research(candles, [], [], baseline_available=True))

    def test_v22_missing_prior_baseline_never_claims_new_evidence(self):
        candles = {"forward_candle_count": 10, "nonconsecutive_intervals": 0}
        self.assertEqual(
            v22.forward_evidence_status(candles, []),
            "NO_PRIOR_FORWARD_BASELINE",
        )
        self.assertFalse(v22.forward_evidence_usable_for_research(candles, []))
        self.assertFalse(v22.forward_evidence_usable_for_research(
            candles, [], ["NO_PRIOR_FORWARD_BASELINE"]))
        self.assertEqual(
            v22.forward_evidence_status(candles, [], baseline_available=True),
            "FORWARD_CANDLES_PRESENT_UNVERIFIED",
        )
        self.assertTrue(v22.forward_evidence_usable_for_research(
            candles, [], baseline_available=True))

    def test_v22_off_grid_candles_are_not_research_evidence(self):
        # Uniformly shifted timestamps preserve 300s deltas but violate the UTC grid.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candles.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["timestamp"])
                writer.writeheader()
                for timestamp in (301, 601, 901):
                    writer.writerow({"timestamp": timestamp})
            candles = v22.inspect_candles(path, 900)
            self.assertEqual(candles["nonconsecutive_intervals"], 0)
            self.assertEqual(candles["off_grid_timestamps"], 3)
            self.assertEqual(
                v22.forward_evidence_status(candles, [], baseline_available=True),
                "INTEGRITY_FAILURE",
            )
            self.assertFalse(
                v22.forward_evidence_usable_for_research(
                    candles, [], baseline_available=True
                )
            )

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
            self.assertEqual(result["off_grid_timestamps"], 0)
            self.assertEqual(result["first_forward_candle_utc"], v22.v17.utc(1200))
            self.assertEqual(result["last_forward_candle_utc"], v22.v17.utc(1500))


if __name__ == "__main__":
    unittest.main(verbosity=2)
