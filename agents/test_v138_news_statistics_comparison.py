import unittest
from news_statistics_comparison_v138 import compare

def fixtures(old=1.5,new=1.0,old_n=10,new_n=5):
    article={"version":"V130.0","matched_articles":10,"categories":[{"category":"ETF","horizons":{
        "5m":{"samples":old_n,"mean_return_pct":old,"median_return_pct":1.2,
              "mean_absolute_move_pct":2.0,"positive_observation_rate_pct":60}}}]}
    adjusted={"version":"V137.0","heuristic_cluster_count":5,"categories":[{"category":"ETF","horizons":{
        "5m":{"samples":new_n,"mean_return_pct":new,"median_return_pct":0.8,
              "mean_absolute_move_pct":1.5,"positive_observation_rate_pct":40}}}]}
    return article,adjusted

class NewsComparisonTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(compare(*fixtures())["version"],"V138.0")
    def test_delta(self):
        row=compare(*fixtures())["rows"][0]
        self.assertEqual(row["changes"]["mean_return_pct"],-0.5)
    def test_sample_reduction(self):
        self.assertEqual(compare(*fixtures())["rows"][0]["potentially_repeated_samples_removed"],5)
    def test_positive_rate_delta(self):
        self.assertEqual(compare(*fixtures())["rows"][0]["changes"]["positive_observation_rate_pct"],-20)
    def test_missing_horizons(self):
        rows=compare(*fixtures())["rows"]
        self.assertEqual(len(rows),3)
        self.assertIsNone(rows[1]["changes"]["mean_return_pct"])
    def test_no_trading(self):
        r=compare(*fixtures())
        self.assertEqual(r["orders_submitted_to_exchange"],0)
        self.assertFalse(r["validated_edge"])
    def test_no_provenance_claim(self):
        self.assertFalse(compare(*fixtures())["same_input_provenance_verified"])
    def test_bad_article_version(self):
        a,b=fixtures()
        a["version"]="V129.0"
        with self.assertRaisesRegex(ValueError,"INVALID_ARTICLE_STATISTICS"):
            compare(a,b)
    def test_bad_adjusted_version(self):
        a,b=fixtures()
        b["version"]="V136.0"
        with self.assertRaisesRegex(ValueError,"INVALID_ADJUSTED_STATISTICS"):
            compare(a,b)
    def test_increased_samples(self):
        with self.assertRaisesRegex(ValueError,"ADJUSTED_SAMPLE_COUNT_EXCEEDS_ARTICLE_COUNT"):
            compare(*fixtures(old_n=2,new_n=3))
    def test_invalid_metric(self):
        a,b=fixtures()
        b["categories"][0]["horizons"]["5m"]["mean_return_pct"]=float("nan")
        with self.assertRaisesRegex(ValueError,"INVALID_METRIC"):
            compare(a,b)
    def test_duplicate_category(self):
        a,b=fixtures()
        a["categories"].append(a["categories"][0])
        with self.assertRaisesRegex(ValueError,"DUPLICATE_CATEGORY"):
            compare(a,b)
    def test_deterministic(self):
        self.assertEqual(compare(*fixtures()),compare(*fixtures()))

if __name__=="__main__":
    unittest.main()
