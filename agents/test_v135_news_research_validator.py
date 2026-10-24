import unittest
from news_research_validator_v135 import validate

def report(times=(0,30),titles=("Bitcoin ETF news","Bitcoin ETF news"),urls=None):
    from datetime import datetime,timedelta,timezone
    start=datetime(2026,10,24,9,tzinfo=timezone.utc)
    urls=urls or ["https://example.org/"+str(i) for i in range(len(times))]
    articles=[{"article_id":str(i),"title":titles[i],"url":urls[i],
        "gdelt_seen_at_utc":(start+timedelta(minutes=minute)).isoformat()}
        for i,minute in enumerate(times)]
    return {"version":"V132.0","collector":{"version":"V127.0","articles":articles},
            "event_study":{"version":"V129.0","events":[{"article_id":str(i)} for i in range(len(times))]}}

class ResearchValidatorTests(unittest.TestCase):
    def test_overlap(self):
        self.assertEqual(len(validate(report())["overlapping_article_pairs"]),1)
    def test_no_overlap(self):
        self.assertEqual(len(validate(report((0,120)))["overlapping_article_pairs"]),0)
    def test_repeated_title(self):
        self.assertEqual(validate(report())["repeated_title_groups"],[["0","1"]])
    def test_distinct_titles(self):
        self.assertEqual(validate(report(titles=("A","B")))["repeated_title_groups"],[])
    def test_repeated_url(self):
        self.assertEqual(validate(report(urls=["https://a.org/x","https://a.org/x"]))["repeated_url_groups"],[["0","1"]])
    def test_no_trading(self):
        r=validate(report())
        self.assertEqual(r["orders_submitted_to_exchange"],0)
        self.assertFalse(r["live_trading_approved"])
        self.assertFalse(r["historical_point_in_time_validated"])
    def test_invalid_pipeline(self):
        with self.assertRaisesRegex(ValueError,"INVALID_PIPELINE"):
            validate({"version":"V131.0"})
    def test_invalid_window(self):
        with self.assertRaisesRegex(ValueError,"INVALID_OVERLAP_WINDOW"):
            validate(report(),0)
    def test_duplicate_ids(self):
        data=report()
        data["collector"]["articles"][1]["article_id"]="0"
        with self.assertRaisesRegex(ValueError,"DUPLICATE_ARTICLE_ID"):
            validate(data)
    def test_missing_event(self):
        data=report()
        data["event_study"]["events"].pop()
        with self.assertRaisesRegex(ValueError,"MISSING_EVENT_ID"):
            validate(data)
    def test_unknown_event(self):
        data=report()
        data["event_study"]["events"][0]["article_id"]="missing"
        with self.assertRaisesRegex(ValueError,"UNKNOWN_EVENT_ID"):
            validate(data)
    def test_determinism(self):
        self.assertEqual(validate(report()),validate(report()))
    def test_empty(self):
        r=validate(report(times=(),titles=()))
        self.assertEqual(r["article_count"],0)

if __name__=="__main__":
    unittest.main()
