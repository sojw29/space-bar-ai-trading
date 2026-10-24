import unittest
from news_intelligence_web_dashboard_v144 import render

def fixture():
    return {"version":"V143.0","data_freshness":"STATIC_OFFLINE_SNAPSHOT",
        "status":"OFFLINE_NEWS_DASHBOARD_VIEW_MODEL",
        "research_only":True,"simulation_only":True,
        "exchange_connected":False,"orders_submitted_to_exchange":0,
        "live_trading_approved":False,"validated_edge":False,
        "causal_effect_established":False,"event_identity_verified":False,
        "first_tradable_news_availability_verified":False,
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
    def test_reject_false_research_only(self):
        data=fixture()
        data["research_only"]=False
        with self.assertRaisesRegex(ValueError,"UNSAFE_DASHBOARD_CONTRACT: research_only"):
            render(data)
    def test_reject_connected_exchange(self):
        data=fixture()
        data["exchange_connected"]=True
        with self.assertRaisesRegex(ValueError,"UNSAFE_DASHBOARD_CONTRACT: exchange_connected"):
            render(data)
    def test_reject_nonzero_orders(self):
        data=fixture()
        data["orders_submitted_to_exchange"]=1
        with self.assertRaisesRegex(ValueError,"UNSAFE_DASHBOARD_CONTRACT: orders_submitted_to_exchange"):
            render(data)
    def test_reject_boolean_order_count(self):
        data=fixture()
        data["orders_submitted_to_exchange"]=False
        with self.assertRaisesRegex(ValueError,"UNSAFE_DASHBOARD_CONTRACT: orders_submitted_to_exchange"):
            render(data)
    def test_reject_missing_safety_flag(self):
        data=fixture()
        del data["simulation_only"]
        with self.assertRaisesRegex(ValueError,"UNSAFE_DASHBOARD_CONTRACT: simulation_only"):
            render(data)
    def test_reject_unverified_edge_claim(self):
        data=fixture()
        data["validated_edge"]=True
        with self.assertRaisesRegex(ValueError,"UNSAFE_DASHBOARD_CONTRACT: validated_edge"):
            render(data)
    def test_reject_wrong_status(self):
        data=fixture()
        data["status"]="LIVE"
        with self.assertRaisesRegex(ValueError,"UNSAFE_DASHBOARD_CONTRACT: status"):
            render(data)
    def test_determinism(self):
        self.assertEqual(render(fixture()),render(fixture()))

if __name__=="__main__":
    unittest.main()
