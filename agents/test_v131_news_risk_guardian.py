import unittest
from news_risk_guardian_v131 import assess

def pipeline(n=10,missing=False):
    ids=[str(i) for i in range(n)]
    collector={"version":"V127.0","articles":[{"article_id":i} for i in ids]}
    taxonomy={"version":"V128.0","articles":[{"article_id":i} for i in ids]}
    study={"version":"V129.0","events":[{"article_id":i,"forward":{"5m":None if missing else {"return_pct":1},"15m":None,"60m":None}} for i in ids]}
    impact={"version":"V130.0","matched_articles":n,"categories":[]}
    return collector,taxonomy,study,impact

def codes(result):
    return [x["code"] for x in result["warnings"]]

class NewsGuardianTests(unittest.TestCase):
    def test_base_warnings(self):
        r=assess(*pipeline())
        self.assertIn("UNVERIFIED_NEWS_AVAILABILITY",codes(r))
        self.assertIn("UNVERIFIED_CAUSALITY",codes(r))
    def test_low_news_sample(self):
        self.assertIn("LOW_NEWS_SAMPLE",codes(assess(*pipeline(3))))
    def test_low_matched_events(self):
        self.assertIn("LOW_MATCHED_EVENTS",codes(assess(*pipeline(3))))
    def test_missing_forward(self):
        self.assertIn("MISSING_FORWARD_RETURNS",codes(assess(*pipeline(missing=True))))
    def test_no_orders(self):
        r=assess(*pipeline())
        self.assertEqual(r["trade_action"],"NONE")
        self.assertEqual(r["orders_submitted_to_exchange"],0)
        self.assertFalse(r["live_trading_approved"])
    def test_invalid_version(self):
        args=list(pipeline())
        args[2]["version"]="V128.0"
        with self.assertRaisesRegex(ValueError,"INVALID_PIPELINE_VERSION"):
            assess(*args)
    def test_invalid_threshold(self):
        with self.assertRaisesRegex(ValueError,"INVALID_THRESHOLDS"):
            assess(*pipeline(),min_articles=0)
    def test_mismatched_articles(self):
        args=list(pipeline())
        args[1]["articles"].pop()
        with self.assertRaisesRegex(ValueError,"PIPELINE_ARTICLE_MISMATCH"):
            assess(*args)
    def test_duplicate_article(self):
        args=list(pipeline())
        args[0]["articles"].append(args[0]["articles"][0])
        with self.assertRaisesRegex(ValueError,"DUPLICATE_ARTICLE_ID"):
            assess(*args)
    def test_invalid_match_count(self):
        args=list(pipeline())
        args[3]["matched_articles"]=2
        with self.assertRaisesRegex(ValueError,"PIPELINE_MATCH_COUNT_MISMATCH"):
            assess(*args)
    def test_determinism(self):
        self.assertEqual(assess(*pipeline()),assess(*pipeline()))
    def test_empty_pipeline(self):
        self.assertIn("LOW_NEWS_SAMPLE",codes(assess(*pipeline(0))))

if __name__=="__main__":
    unittest.main()
