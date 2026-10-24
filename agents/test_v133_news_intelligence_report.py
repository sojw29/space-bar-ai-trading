import unittest
from news_intelligence_report_v133 import render

def sample():
    return {
        "version":"V132.0",
        "collector":{"version":"V127.0","topic":"BTC","count":5},
        "taxonomy":{"version":"V128.0","category_counts":{"ETF":5}},
        "event_study":{"version":"V129.0","event_count":5},
        "impact":{"version":"V130.0","matched_articles":5,"categories":[
            {"category":"ETF","horizons":{"5m":{"samples":5,"mean_return_pct":0.3,
                "median_return_pct":0.2,"mean_absolute_move_pct":0.5,
                "positive_observation_rate_pct":60}}}]},
        "guardian":{"version":"V131.0","warning_count":1,"warnings":[
            {"code":"UNVERIFIED_NEWS_AVAILABILITY","detail":"Observed time only."}]}
    }

class NewsReportTests(unittest.TestCase):
    def test_title(self):
        self.assertIn("V133 News Intelligence",render(sample()))
    def test_topic(self):
        self.assertIn("News topic: BTC",render(sample()))
    def test_category(self):
        self.assertIn("| ETF | 5 |",render(sample()))
    def test_forward_return(self):
        self.assertIn("0.3000%",render(sample()))
    def test_positive_rate(self):
        self.assertIn("60.0000%",render(sample()))
    def test_warning(self):
        self.assertIn("UNVERIFIED_NEWS_AVAILABILITY",render(sample()))
    def test_missing_horizon(self):
        self.assertIn("N/A (insufficient samples)",render(sample()))
    def test_no_trading_claim(self):
        self.assertIn("cannot trigger orders",render(sample()))
    def test_invalid_version(self):
        data=sample()
        data["version"]="V131.0"
        with self.assertRaisesRegex(ValueError,"INVALID_V132_REPORT"):
            render(data)
    def test_incomplete(self):
        data=sample()
        data.pop("guardian")
        with self.assertRaisesRegex(ValueError,"INCOMPLETE_PIPELINE_REPORT"):
            render(data)
    def test_invalid_category(self):
        data=sample()
        data["taxonomy"]["category_counts"]["ETF"]="five"
        with self.assertRaisesRegex(ValueError,"INVALID_CATEGORY_COUNTS"):
            render(data)
    def test_determinism(self):
        self.assertEqual(render(sample()),render(sample()))
    def test_no_warning(self):
        data=sample()
        data["guardian"]["warnings"]=[]
        self.assertIn("general limitations",render(data))

if __name__=="__main__":
    unittest.main()
