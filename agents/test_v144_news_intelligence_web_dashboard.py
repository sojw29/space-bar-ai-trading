import unittest
from news_intelligence_web_dashboard_v144 import render

def fixture():
    return {"version":"V143.0","data_freshness":"STATIC_OFFLINE_SNAPSHOT",
        "metadata":{"topic":"BTC","observed_at":"2026-10-24T09:00:00Z",
                    "replay_verified_this_run":False},
        "cards":[{"id":"article_count","label":"Articles","value":3}],
        "charts":[{"category":"ETF","horizon":"5m","article_samples":3,
                   "adjusted_samples":2,"removed_samples":1,
                   "mean_return_delta_percentage_points":-0.25,
                   "positive_rate_delta_percentage_points":None}],
        "warning_codes":["LOW_NEWS_SAMPLE"]}

class OfflineDashboardTests(unittest.TestCase):
    def test_html(self):
        self.assertIn("<!doctype html>",render(fixture()))
    def test_card(self):
        self.assertIn("Articles",render(fixture()))
    def test_comparison(self):
        self.assertIn("-0.2500",render(fixture()))
    def test_missing_metric(self):
        self.assertIn("N/A",render(fixture()))
    def test_warning(self):
        self.assertIn("LOW_NEWS_SAMPLE",render(fixture()))
    def test_no_network_resources(self):
        result=render(fixture())
        self.assertNotIn("<script",result)
        self.assertNotIn("<link",result)
    def test_escaped_category(self):
        data=fixture()
        data["charts"][0]["category"]="<script>alert(1)</script>"
        result=render(data)
        self.assertNotIn("<script",result)
        self.assertIn("&lt;script&gt;",result)
    def test_escaped_topic(self):
        data=fixture()
        data["metadata"]["topic"]="<img src=x>"
        self.assertIn("&lt;img",render(data))
    def test_replay_verified(self):
        data=fixture()
        data["metadata"]["replay_verified_this_run"]=True
        self.assertIn("Exact replay: <strong>YES",render(data))
    def test_reject_live(self):
        data=fixture()
        data["data_freshness"]="LIVE"
        with self.assertRaisesRegex(ValueError,"UNSUPPORTED_DATA_FRESHNESS"):
            render(data)
    def test_reject_bad_counts(self):
        data=fixture()
        data["charts"][0]["removed_samples"]=2
        with self.assertRaisesRegex(ValueError,"INCONSISTENT_CHART_COUNTS"):
            render(data)
    def test_reject_nan(self):
        data=fixture()
        data["charts"][0]["mean_return_delta_percentage_points"]=float("nan")
        with self.assertRaisesRegex(ValueError,"INVALID_METRIC"):
            render(data)
    def test_determinism(self):
        self.assertEqual(render(fixture()),render(fixture()))

if __name__=="__main__":
    unittest.main()
