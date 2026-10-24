import tempfile
import unittest
from pathlib import Path

from news_data_provenance_v139 import ROLES,manifest
from news_verified_statistics_comparison_v140 import verified_compare

SETTINGS={"topic":"BTC","observed_at":"2026-10-24T10:00:00Z",
          "min_samples":5,"cluster_window_minutes":60}

def aggregates():
    original={"version":"V130.0","matched_articles":10,"categories":[{"category":"ETF",
        "horizons":{"5m":{"samples":10,"mean_return_pct":1.5,
                          "median_return_pct":1.0,"mean_absolute_move_pct":2.0,
                          "positive_observation_rate_pct":60}}}]}
    adjusted={"version":"V137.0","heuristic_cluster_count":5,"categories":[{"category":"ETF",
        "horizons":{"5m":{"samples":5,"mean_return_pct":1.0,
                          "median_return_pct":0.8,"mean_absolute_move_pct":1.5,
                          "positive_observation_rate_pct":40}}}]}
    return original,adjusted

class VerifiedComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.paths={}
        for role in ROLES:
            path=Path(self.tmp.name)/role
            path.write_text(role,encoding="utf-8")
            self.paths[role]=path
        self.provenance=manifest(self.paths,SETTINGS)
    def test_matching_inputs(self):
        r=verified_compare(*aggregates(),self.provenance,self.provenance)
        self.assertEqual(r["version"],"V140.0")
        self.assertTrue(r["input_bytes_and_declared_settings_match"])
    def test_delta(self):
        r=verified_compare(*aggregates(),self.provenance,self.provenance)
        self.assertEqual(r["comparison"]["rows"][0]["changes"]["mean_return_pct"],-0.5)
    def test_fail_closed_changed_file(self):
        self.paths["raw_news"].write_text("changed",encoding="utf-8")
        different=manifest(self.paths,SETTINGS)
        with self.assertRaisesRegex(ValueError,"INPUT_PROVENANCE_MISMATCH"):
            verified_compare(*aggregates(),self.provenance,different)
    def test_fail_closed_changed_setting(self):
        different=manifest(self.paths,{**SETTINGS,"cluster_window_minutes":30})
        with self.assertRaisesRegex(ValueError,"INPUT_PROVENANCE_MISMATCH"):
            verified_compare(*aggregates(),self.provenance,different)
    def test_fail_closed_bad_manifest(self):
        broken=dict(self.provenance)
        broken["manifest_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"MANIFEST_DIGEST_MISMATCH"):
            verified_compare(*aggregates(),self.provenance,broken)
    def test_bad_aggregate(self):
        a,b=aggregates()
        b["version"]="V136.0"
        with self.assertRaisesRegex(ValueError,"INVALID_ADJUSTED_STATISTICS"):
            verified_compare(a,b,self.provenance,self.provenance)
    def test_not_output_lineage_proven(self):
        r=verified_compare(*aggregates(),self.provenance,self.provenance)
        self.assertFalse(r["statistics_derived_from_manifest_inputs_verified"])
    def test_not_tradable_news_proven(self):
        r=verified_compare(*aggregates(),self.provenance,self.provenance)
        self.assertFalse(r["news_first_market_availability_verified"])
    def test_no_orders(self):
        r=verified_compare(*aggregates(),self.provenance,self.provenance)
        self.assertEqual(r["orders_submitted_to_exchange"],0)
        self.assertFalse(r["live_trading_approved"])
    def test_deterministic(self):
        self.assertEqual(verified_compare(*aggregates(),self.provenance,self.provenance),
                         verified_compare(*aggregates(),self.provenance,self.provenance))
    def test_missing_horizon(self):
        r=verified_compare(*aggregates(),self.provenance,self.provenance)
        self.assertIsNone(r["comparison"]["rows"][1]["changes"]["mean_return_pct"])
    def test_samples_removed(self):
        r=verified_compare(*aggregates(),self.provenance,self.provenance)
        self.assertEqual(r["comparison"]["rows"][0]["potentially_repeated_samples_removed"],5)

if __name__=="__main__":
    unittest.main()
