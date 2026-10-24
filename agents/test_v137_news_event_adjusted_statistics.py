import unittest
from news_event_adjusted_statistics_v137 import adjust

def fixture(returns=(1.0,5.0,3.0),groups=(("a","b"),("c",))):
    taxonomy={"version":"V128.0","articles":[{"article_id":aid,"categories":["ETF"]}
        for aid in ("a","b","c")]}
    event={"version":"V129.0","events":[{"article_id":aid,
        "gdelt_seen_at_utc":"2026-10-24T09:0"+str(i)+":00+00:00",
        "forward":{"5m":{"return_pct":returns[i]}}}
        for i,aid in enumerate(("a","b","c"))]}
    clusters={"version":"V136.0","clusters":[{"article_ids":list(ids)} for ids in groups]}
    return taxonomy,event,clusters

class AdjustedNewsStatisticsTests(unittest.TestCase):
    def test_representatives(self):
        r=adjust(*fixture(),min_samples=1)
        self.assertEqual(r["representative_article_ids"],["a","c"])
    def test_removed_count(self):
        self.assertEqual(adjust(*fixture(),min_samples=1)["excluded_potential_duplicate_articles"],1)
    def test_mean_uses_one_per_group(self):
        r=adjust(*fixture(),min_samples=1)
        self.assertEqual(r["categories"][0]["horizons"]["5m"]["mean_return_pct"],2)
    def test_min_samples_suppresses(self):
        r=adjust(*fixture(),min_samples=3)
        self.assertIsNone(r["categories"][0]["horizons"]["5m"]["mean_return_pct"])
    def test_missing_horizon(self):
        r=adjust(*fixture(),min_samples=1)
        self.assertEqual(r["categories"][0]["horizons"]["15m"]["samples"],0)
    def test_no_orders(self):
        r=adjust(*fixture(),min_samples=1)
        self.assertEqual(r["orders_submitted_to_exchange"],0)
        self.assertFalse(r["validated_edge"])
    def test_invalid_min_samples(self):
        with self.assertRaisesRegex(ValueError,"INVALID_MIN_SAMPLES"):
            adjust(*fixture(),min_samples=0)
    def test_invalid_taxonomy(self):
        a,b,c=fixture()
        a["version"]="V127.0"
        with self.assertRaisesRegex(ValueError,"INVALID_TAXONOMY"):
            adjust(a,b,c)
    def test_missing_coverage(self):
        a,b,c=fixture(groups=(("a","b"),))
        with self.assertRaisesRegex(ValueError,"UNCOVERED_ARTICLES"):
            adjust(a,b,c)
    def test_repeated_membership(self):
        a,b,c=fixture(groups=(("a","b"),("b","c")))
        with self.assertRaisesRegex(ValueError,"INVALID_CLUSTER_MEMBERSHIP"):
            adjust(a,b,c)
    def test_determinism(self):
        self.assertEqual(adjust(*fixture(),min_samples=1),adjust(*fixture(),min_samples=1))
    def test_reverse_cluster_ids(self):
        r=adjust(*fixture(groups=(("b","a"),("c",))),min_samples=1)
        self.assertEqual(r["representative_article_ids"],["a","c"])

if __name__=="__main__":
    unittest.main()
