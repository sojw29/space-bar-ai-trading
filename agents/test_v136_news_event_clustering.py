import unittest
from datetime import datetime,timedelta,timezone
from news_event_clustering_v136 import cluster

START=datetime(2026,10,24,9,tzinfo=timezone.utc)
def snapshot(rows):
    return {"version":"V127.0","articles":[{"article_id":str(i),"title":title,
        "url":url,"gdelt_seen_at_utc":(START+timedelta(minutes=minute)).isoformat()}
        for i,(minute,title,url) in enumerate(rows)]}
def article(minute=0,title="BTC ETF",url="https://example.org/a"):
    return (minute,title,url)

class NewsEventClusteringTests(unittest.TestCase):
    def test_exact_title_nearby(self):
        r=cluster(snapshot([article(),article(30,url="https://other.org/b")]))
        self.assertEqual(r["cluster_count"],1)
    def test_exact_url_nearby(self):
        r=cluster(snapshot([article(),article(30,title="Different title")]))
        self.assertEqual(r["cluster_count"],1)
    def test_proximity_alone_not_enough(self):
        r=cluster(snapshot([article(),article(1,"ETH news","https://other.org/b")]))
        self.assertEqual(r["cluster_count"],2)
    def test_far_apart_not_clustered(self):
        r=cluster(snapshot([article(),article(120)]))
        self.assertEqual(r["cluster_count"],2)
    def test_transitive_chain_restricted(self):
        r=cluster(snapshot([article(),article(40),article(80)]))
        self.assertEqual(r["cluster_count"],2)
    def test_title_case_whitespace(self):
        r=cluster(snapshot([article(),article(2," btc   etf ","https://other.org/b")]))
        self.assertEqual(r["cluster_count"],1)
    def test_empty(self):
        self.assertEqual(cluster(snapshot([]))["cluster_count"],0)
    def test_duplicate_ids(self):
        data=snapshot([article(),article()])
        data["articles"][1]["article_id"]="0"
        with self.assertRaisesRegex(ValueError,"DUPLICATE_ARTICLE_ID"):
            cluster(data)
    def test_bad_version(self):
        with self.assertRaisesRegex(ValueError,"INVALID_V127_SNAPSHOT"):
            cluster({"version":"V128.0","articles":[]})
    def test_naive_time(self):
        data=snapshot([article()])
        data["articles"][0]["gdelt_seen_at_utc"]="2026-10-24T09:00:00"
        with self.assertRaisesRegex(ValueError,"INVALID_SEEN_TIME"):
            cluster(data)
    def test_invalid_window(self):
        with self.assertRaisesRegex(ValueError,"INVALID_WINDOW"):
            cluster(snapshot([]),0)
    def test_no_orders(self):
        r=cluster(snapshot([article()]))
        self.assertEqual(r["orders_submitted_to_exchange"],0)
        self.assertFalse(r["live_trading_approved"])
        self.assertFalse(r["event_identity_verified"])
    def test_deterministic(self):
        data=snapshot([article(),article(2)])
        self.assertEqual(cluster(data),cluster(data))
    def test_repeated_count(self):
        r=cluster(snapshot([article(),article(2),article(5)]))
        self.assertEqual(r["potentially_repeated_articles"],2)

if __name__=="__main__":
    unittest.main()
