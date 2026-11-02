"""Offline regression checks for V18-V22. No exchange access required."""
import csv
import json
import os
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
    def test_v22_previous_output_alias_rejected_before_deletion(self):
        for kind in ("same","hardlink","symlink"):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                target=root/"evidence.json"
                target.write_bytes(b"preserve prior evidence")
                prior=target if kind=="same" else root/"prior.json"
                if kind=="hardlink":os.link(target,prior)
                if kind=="symlink":prior.symlink_to(target)
                with patch.object(v22,"OUT",root),patch.object(v22,"previous_evidence_path",return_value=prior),patch.object(v22.v21,"run",side_effect=RuntimeError("upstream failed")) as upstream:
                    with self.assertRaisesRegex(ValueError,"INPUT_OUTPUT_PATH_COLLISION"):v22.run()
                upstream.assert_not_called()
                self.assertEqual(target.read_bytes(),b"preserve prior evidence")
                self.assertEqual(prior.read_bytes(),b"preserve prior evidence")

    def test_v22_atomic_publication_preserves_symlink_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            unrelated=root/"unrelated.json"
            unrelated.write_bytes(b"preserve me")
            target=root/"evidence.json"
            target.symlink_to(unrelated)
            with patch.object(v22,"OUT",root):v22.publish_evidence({"integrity_pass":True})
            self.assertEqual(unrelated.read_bytes(),b"preserve me")
            self.assertFalse(target.is_symlink())
            self.assertEqual(json.loads(target.read_text()),{"integrity_pass":True})
            self.assertEqual(list(root.glob(".evidence.json.*.tmp")),[])

    def test_v22_publication_failure_cleans_temporary_output(self):
        for serialization in (False,True):
            with self.subTest(serialization=serialization),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                report={"invalid":float("nan")} if serialization else {"integrity_pass":True}
                with patch.object(v22,"OUT",root),patch.object(v22.os,"replace",side_effect=OSError("injected replace failure")):
                    with self.assertRaises((OSError,ValueError)):v22.publish_evidence(report)
                self.assertFalse((root/"evidence.json").exists())
                self.assertEqual(list(root.glob(".evidence.json.*.tmp")),[])


    def test_v22_failed_upstream_run_removes_stale_pass_report(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "v22"
            out.mkdir()
            stale = out / "evidence.json"
            stale.write_text('{"integrity_pass": true}', encoding="utf-8")
            with patch.object(v22, "OUT", out), \
                 patch.object(v21, "run", side_effect=RuntimeError("UPSTREAM_FAILURE")):
                with self.assertRaisesRegex(RuntimeError, "UPSTREAM_FAILURE"):
                    v22.run()
            self.assertFalse(stale.exists())

    def test_v22_corrupt_prior_run_removes_stale_pass_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "v22"
            out.mkdir()
            stale = out / "evidence.json"
            stale.write_text('{"integrity_pass": true}', encoding="utf-8")
            source = root / "v17"
            source.mkdir()
            (source / "protocol.json").write_text("{}", encoding="utf-8")
            (source / "summary.csv").write_text("candidate,scenario\n", encoding="utf-8")
            candles = root / "candles.csv"
            candles.write_text("timestamp\n", encoding="utf-8")
            prior = root / "prior.json"
            prior.write_text("null", encoding="utf-8")
            with patch.object(v22, "OUT", out), \
                 patch.object(v22, "CANDLE_PATH", candles), \
                 patch.object(v17, "REPORT_DIR", source), \
                 patch.object(v21, "run", return_value=None), \
                 patch.object(v22, "inspect_candles", return_value={}), \
                 patch.object(v22, "previous_evidence_path", return_value=prior):
                with self.assertRaisesRegex(RuntimeError, "INVALID_PRIOR_EVIDENCE_SCHEMA"):
                    v22.run()
            self.assertFalse(stale.exists())

    def test_v22_corrupt_prior_files_are_not_missing_baselines(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"evidence.json"
            self.assertIsNone(v22.load_previous_evidence(path))
            for content in ("null","[]","false","123",'"text"',"{}",'{"candles":[]}', '{"candles":null}',"invalid JSON"):
                with self.subTest(content=content):
                    path.write_text(content,encoding="utf-8")
                    with self.assertRaisesRegex(RuntimeError,"INVALID_PRIOR_EVIDENCE"):
                        v22.load_previous_evidence(path)
                    self.assertEqual(path.read_text(encoding="utf-8"),content)

    def test_v22_valid_legacy_and_current_prior_files_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"evidence.json"
            for prior in ({"candles":{}},{"candles":{},"history_policy":v22.history_policy()}):
                path.write_text(json.dumps(prior),encoding="utf-8")
                self.assertEqual(v22.load_previous_evidence(path),prior)

    def test_v22_invalid_prior_shapes_fail_comparison_explicitly(self):
        for prior in ([],False,123,"text",{}, {"candles":[]}, {"candles":None}):
            with self.subTest(prior=prior):
                self.assertEqual(v22.compare_forward_snapshot(prior,"2026-10-25T00:00:00+00:00"),(["INVALID_PRIOR_EVIDENCE_SCHEMA"],[],False))


    def test_v22_compares_forward_instants_not_timestamp_strings(self):
        prior={"history_policy":v22.history_policy(),"candles":{"last_forward_candle_utc":"2026-10-25T09:00:00+09:00"}}
        self.assertEqual(v22.compare_forward_snapshot(prior,"2026-10-25T00:00:00+00:00"),([], ["NO_NEW_FORWARD_CANDLES"],True))
        self.assertEqual(v22.compare_forward_snapshot(prior,"2026-10-25T01:00:00+00:00"),([],[],True))
        prior["candles"]["last_forward_candle_utc"]="2026-10-25T00:00:00+00:00"
        self.assertEqual(v22.compare_forward_snapshot(prior,"2026-10-25T08:00:00+09:00"),(["FORWARD_DATA_REGRESSION"],[],True))

    def test_v22_rejects_malformed_comparable_timestamps(self):
        for bad in ("garbage","2026-10-25T00:00:00",123,True):
            with self.subTest(bad=bad):
                prior={"history_policy":v22.history_policy(),"candles":{"last_forward_candle_utc":bad}}
                issues,warnings,baseline=v22.compare_forward_snapshot(prior,"2026-10-25T00:00:00+00:00")
                self.assertEqual(issues,["INVALID_PRIOR_FORWARD_TIMESTAMP"])
                self.assertFalse(baseline)
                prior["candles"]["last_forward_candle_utc"]="2026-10-25T00:00:00+00:00"
                issues,warnings,baseline=v22.compare_forward_snapshot(prior,bad)
                self.assertEqual(issues,["INVALID_CURRENT_FORWARD_TIMESTAMP"])
                self.assertFalse(baseline)


    def test_v22_archive_policy_change_requires_new_baseline(self):
        prior={"candles":{"last_forward_candle_utc":"2026-10-29T00:00:00+00:00"}}
        for policy in (None,dict(v22.history_policy(),publication_delay_days=3)):
            with self.subTest(policy=policy):
                prior["history_policy"]=policy
                issues,warnings,baseline=v22.compare_forward_snapshot(prior,"2026-10-25T00:00:00+00:00")
                self.assertEqual(issues,[])
                self.assertIn("PRIOR_HISTORY_POLICY_INCOMPARABLE",warnings)
                self.assertFalse(baseline)
                candles={"forward_candle_count":2016,"nonconsecutive_intervals":0}
                self.assertFalse(v22.forward_evidence_usable_for_research(candles,issues,warnings,baseline))

    def test_v22_same_policy_still_rejects_regression(self):
        prior={"history_policy":v22.history_policy(),"candles":{"last_forward_candle_utc":"2026-10-25T00:00:00+00:00"}}
        issues,warnings,baseline=v22.compare_forward_snapshot(prior,"2026-10-24T00:00:00+00:00")
        self.assertEqual(issues,["FORWARD_DATA_REGRESSION"])
        self.assertTrue(baseline)
        self.assertEqual(v22.compare_forward_snapshot(prior,"2026-10-25T00:00:00+00:00"),([], ["NO_NEW_FORWARD_CANDLES"],True))
        self.assertEqual(v22.compare_forward_snapshot(prior,"2026-10-26T00:00:00+00:00"),([],[],True))

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
