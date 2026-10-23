"""Offline unit tests for V63 observation diagnostics."""
import unittest
from datetime import datetime, timezone
from observation_diagnostics_v63 import diagnose

NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)

def inputs():
    return ({"observed_last_candle_utc": "2026-10-22T00:00:00+00:00", "integrity_pass": True},
            {"integrity_pass": True},
            {"current_finalized_by_candidate_scenario": {"BTC": {"BASE": 1, "STRESS": 2}}},
            {"candidates": []})

class DiagnosticsTests(unittest.TestCase):
    def test_valid_evidence_is_observation_only(self):
        self.assertEqual(diagnose(*inputs(), now=NOW)["status"], "OBSERVATION_ONLY")

    def test_stale_data_warning(self):
        a, b, c, d = inputs()
        a["observed_last_candle_utc"] = "2026-10-01T00:00:00Z"
        self.assertIn("STALE_CANDLES", diagnose(a, b, c, d, now=NOW)["warnings"])

    def test_future_data_fails(self):
        a, b, c, d = inputs()
        a["observed_last_candle_utc"] = "2026-10-24T00:00:00Z"
        self.assertIn("FUTURE_LAST_CANDLE", diagnose(a, b, c, d, now=NOW)["errors"])

    def test_missing_integrity_fails(self):
        a, b, c, d = inputs()
        self.assertEqual(diagnose(a, None, c, d, now=NOW)["status"], "FAIL")

    def test_invalid_counts_fail(self):
        a, b, c, d = inputs()
        c["current_finalized_by_candidate_scenario"]["BTC"]["BASE"] = True
        self.assertIn("INVALID_FINALIZED_COUNTS", diagnose(a, b, c, d, now=NOW)["errors"])

    def test_zero_samples_not_success(self):
        a, b, c, d = inputs()
        c["current_finalized_by_candidate_scenario"] = {}
        self.assertEqual(diagnose(a, b, c, d, now=NOW)["status"], "NEEDS_MORE_EVIDENCE")

if __name__ == "__main__":
    unittest.main()
