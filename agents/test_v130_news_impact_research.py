import unittest
from news_impact_research_v130 import aggregate

def taxonomy(n=5,category="ETF"):
    return {"version":"V128.0","articles":[{"article_id":str(i),"categories":[category]} for i in range(n)]}
def events(n=5,value=1):
    return {"version":"V129.0","events":[{"article_id":str(i),"forward":{
        "5m":{"return_pct":value},"15m":{"return_pct":-value},"60m":None}} for i in range(n)]}
def cat(result):
    return result["categories"][0]["horizons"]

class NewsImpactTests(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(cat(aggregate(taxonomy(),events()))["5m"]["mean_return_pct"],1)
    def test_median(self):
        self.assertEqual(cat(aggregate(taxonomy(),events()))["15m"]["median_return_pct"],-1)
    def test_absolute_move(self):
        self.assertEqual(cat(aggregate(taxonomy(),events()))["15m"]["mean_absolute_move_pct"],1)
    def test_positive_rate(self):
        self.assertEqual(cat(aggregate(taxonomy(),events()))["5m"]["positive_observation_rate_pct"],100)
    def test_missing_horizon(self):
        self.assertIsNone(cat(aggregate(taxonomy(),events()))["60m"]["mean_return_pct"])
    def test_small_sample_suppressed(self):
        self.assertIsNone(cat(aggregate(taxonomy(3),events(3)))["5m"]["mean_return_pct"])
    def test_small_sample_count_visible(self):
        self.assertEqual(cat(aggregate(taxonomy(3),events(3)))["5m"]["samples"],3)
    def test_unmatched_articles(self):
        self.assertEqual(aggregate(taxonomy(6),events(5))["matched_articles"],5)
    def test_no_approval(self):
        r=aggregate(taxonomy(),events())
        self.assertFalse(r["live_trading_approved"])
        self.assertFalse(r["causal_effect_established"])
        self.assertEqual(r["orders_submitted_to_exchange"],0)
    def test_bad_version(self):
        with self.assertRaisesRegex(ValueError,"INVALID_V128_TAXONOMY"):
            aggregate({"version":"V127.0"},events())
    def test_duplicate_events(self):
        data=events()
        data["events"].append(data["events"][0])
        with self.assertRaisesRegex(ValueError,"DUPLICATE_EVENT_ID"):
            aggregate(taxonomy(),data)
    def test_duplicate_articles(self):
        data=taxonomy()
        data["articles"].append(data["articles"][0])
        with self.assertRaisesRegex(ValueError,"DUPLICATE_ARTICLE_ID"):
            aggregate(data,events())
    def test_nonfinite(self):
        data=events()
        data["events"][0]["forward"]["5m"]["return_pct"]=float("nan")
        with self.assertRaisesRegex(ValueError,"INVALID_RETURN"):
            aggregate(taxonomy(),data)
    def test_invalid_min_samples(self):
        with self.assertRaisesRegex(ValueError,"INVALID_MIN_SAMPLES"):
            aggregate(taxonomy(),events(),0)
    def test_deterministic(self):
        self.assertEqual(aggregate(taxonomy(),events()),aggregate(taxonomy(),events()))

if __name__=="__main__":
    unittest.main()
