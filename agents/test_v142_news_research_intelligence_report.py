import unittest
from news_research_intelligence_report_v142 import render
from news_research_reproducibility_v141 import ARTIFACTS

def fixture():
    items={name:{} for name in ARTIFACTS}
    items["pipeline"]={"version":"V132.0","guardian":{"warnings":[{"code":"UNVERIFIED_CAUSALITY"}]}}
    items["clusters"]={"version":"V136.0","article_count":2,"cluster_count":1,
                       "potentially_repeated_articles":1}
    items["adjusted_statistics"]={"version":"V137.0"}
    items["comparison"]={"version":"V138.0","rows":[{
        "category":"ETF","horizon":"5m","article_samples":2,
        "cluster_adjusted_samples":1,"potentially_repeated_samples_removed":1,
        "changes":{"mean_return_pct":-0.25,"positive_observation_rate_pct":-20}}]}
    bundle={"version":"V141.0","input_manifest":{"settings":{
        "topic":"BTC","observed_at":"2026-10-24T09:00:00Z"},
        "manifest_sha256":"abc"}}
    return bundle,items

class NewsReportTests(unittest.TestCase):
    def test_header(self):
        self.assertIn("News Research Intelligence Report",render(*fixture()))
    def test_category(self):
        self.assertIn("ETF | 5m",render(*fixture()))
    def test_negative_delta(self):
        self.assertIn("-0.2500",render(*fixture()))
    def test_research_warning(self):
        self.assertIn("UNVERIFIED_CAUSALITY",render(*fixture()))
    def test_not_checked(self):
        self.assertIn("NOT CHECKED",render(*fixture()))
    def test_replay_checked(self):
        self.assertIn("YES",render(*fixture(),verification={"reproducible":True}))
    def test_no_trading_claim(self):
        self.assertIn("No exchange orders",render(*fixture()))
    def test_escape_category(self):
        a,b=fixture()
        b["comparison"]["rows"][0]["category"]="A|B"
        self.assertIn("A\\|B",render(a,b))
    def test_missing_metric(self):
        a,b=fixture()
        b["comparison"]["rows"][0]["changes"]["mean_return_pct"]=None
        self.assertIn("N/A",render(a,b))
    def test_invalid_metric(self):
        a,b=fixture()
        b["comparison"]["rows"][0]["changes"]["mean_return_pct"]=float("nan")
        with self.assertRaisesRegex(ValueError,"INVALID_METRIC"):
            render(a,b)
    def test_invalid_version(self):
        a,b=fixture()
        a["version"]="V140.0"
        with self.assertRaisesRegex(ValueError,"INVALID_BUNDLE"):
            render(a,b)
    def test_deterministic(self):
        self.assertEqual(render(*fixture()),render(*fixture()))

if __name__=="__main__":
    unittest.main()
