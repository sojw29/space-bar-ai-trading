import unittest
from unittest.mock import patch
from news_collector_v127 import normalize,fetch,QUERIES

NOW="2026-10-24T12:00:00+00:00"
def article(url="https://example.org/a",seen="20261024090000",title="BTC market"):
    return {"url":url,"seendate":seen,"title":title,"domain":"example.org"}

class NewsCollectorTests(unittest.TestCase):
    def test_valid_article(self):
        r=normalize({"articles":[article()]},"BTC",NOW)
        self.assertEqual(r["count"],1)
        self.assertFalse(r["articles"][0]["original_publication_time_verified"])
    def test_duplicate_dedup(self):
        r=normalize({"articles":[article(),article()]},"BTC",NOW)
        self.assertEqual(r["count"],1)
    def test_future_seen_rejected(self):
        self.assertEqual(normalize({"articles":[article(seen="20261025120000")]},"BTC",NOW)["count"],0)
    def test_invalid_timestamp_rejected(self):
        self.assertEqual(normalize({"articles":[article(seen="invalid")]},"BTC",NOW)["count"],0)
    def test_non_https_rejected(self):
        self.assertEqual(normalize({"articles":[article(url="http://example.org/a")]},"BTC",NOW)["count"],0)
    def test_no_credentials_in_url(self):
        self.assertEqual(normalize({"articles":[article(url="https://u:p@example.org/a")]},"BTC",NOW)["count"],0)
    def test_invalid_topic(self):
        with self.assertRaisesRegex(ValueError,"INVALID_TOPIC"):
            normalize({"articles":[]},"DOGE",NOW)
    def test_invalid_payload(self):
        with self.assertRaisesRegex(ValueError,"INVALID_GDELT_RESPONSE"):
            normalize({},"BTC",NOW)
    def test_missing_timezone(self):
        with self.assertRaisesRegex(ValueError,"INVALID_OBSERVATION_TIME"):
            normalize({"articles":[]},"BTC","2026-10-24T12:00:00")
    def test_empty_response(self):
        self.assertEqual(normalize({"articles":[]},"MACRO",NOW)["count"],0)
    def test_deterministic(self):
        data={"articles":[article(),article(url="https://example.org/b")]}
        self.assertEqual(normalize(data,"BTC",NOW),normalize(data,"BTC",NOW))
    def test_no_live_orders(self):
        r=normalize({"articles":[article()]},"ETH",NOW)
        self.assertFalse(r["live_trading_approved"])
        self.assertEqual(r["orders_submitted_to_exchange"],0)
    def test_fetch_invalid_timespan_without_network(self):
        with self.assertRaisesRegex(ValueError,"INVALID_TIMESPAN"):
            fetch("BTC","yesterday")
    def test_fetch_mocked_network(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self,n): return b'{"articles":[]}'
        with patch("news_collector_v127.urllib.request.urlopen",return_value=Response()) as mocked:
            self.assertEqual(fetch("BTC")["articles"],[])
            self.assertTrue(mocked.called)
    def test_topics(self):
        self.assertEqual(set(QUERIES),{"BTC","ETH","SOL","MACRO"})

if __name__=="__main__":
    unittest.main()
