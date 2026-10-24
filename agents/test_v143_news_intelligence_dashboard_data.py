import unittest
from news_intelligence_dashboard_data_v143 import build

def fixture():
    bundle={"version":"V141.0","input_manifest":{
        "settings":{"topic":"BTC","observed_at":"2026-10-24T09:00:00Z"},
        "manifest_sha256":"abc"}}
    artifacts={
        "pipeline":{"version":"V132.0","guardian":{"warnings":[{"code":"LOW_NEWS_SAMPLE"}]}},
        "clusters":{"version":"V136.0","article_count":3,"cluster_count":2,
                    "potentially_repeated_articles":1},
        "adjusted_statistics":{"version":"V137.0"},
        "comparison":{"version":"V138.0","rows":[{"category":"ETF","horizon":"5m",
            "article_samples":3,"cluster_adjusted_samples":2,
            "changes":{"mean_return_pct":-0.2,"positive_observation_rate_pct":-10}}]}}
    return bundle,artifacts

class DashboardDataTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(build(*fixture())["version"],"V143.0")
    def test_cards(self):
        self.assertEqual(build(*fixture())["cards"][0]["value"],3)
    def test_charts(self):
        self.assertEqual(build(*fixture())["charts"][0]["removed_samples"],1)
    def test_delta(self):
        self.assertEqual(build(*fixture())["charts"][0]["mean_return_delta_percentage_points"],-0.2)
    def test_warnings(self):
        self.assertIn("LOW_NEWS_SAMPLE",build(*fixture())["warning_codes"])
    def test_static(self):
        self.assertEqual(build(*fixture())["data_freshness"],"STATIC_OFFLINE_SNAPSHOT")
    def test_replay_default_false(self):
        self.assertFalse(build(*fixture())["metadata"]["replay_verified_this_run"])
    def test_replay_true(self):
        self.assertTrue(build(*fixture(),verification={"reproducible":True})["metadata"]["replay_verified_this_run"])
    def test_inconsistent_counts(self):
        a,b=fixture()
        b["clusters"]["cluster_count"]=3
        with self.assertRaisesRegex(ValueError,"INCONSISTENT_COUNTS"):
            build(a,b)
    def test_invalid_metric(self):
        a,b=fixture()
        b["comparison"]["rows"][0]["changes"]["mean_return_pct"]=float("nan")
        with self.assertRaisesRegex(ValueError,"INVALID_DASHBOARD_METRIC"):
            build(a,b)
    def test_no_orders(self):
        r=build(*fixture())
        self.assertEqual(r["orders_submitted_to_exchange"],0)
        self.assertFalse(r["live_trading_approved"])
    def test_determinism(self):
        self.assertEqual(build(*fixture()),build(*fixture()))

if __name__=="__main__":
    unittest.main()
