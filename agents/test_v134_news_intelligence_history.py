import unittest
from news_intelligence_history_v134 import record,compare,summarize

WHEN="2026-10-24T09:00:00+00:00"
def report(value=1):
    return {"version":"V132.0","impact":{"version":"V130.0","matched_articles":6,
        "categories":[{"category":"ETF","horizons":{"5m":{
            "samples":6,"mean_return_pct":value,"median_return_pct":value,
            "mean_absolute_move_pct":abs(value),"positive_observation_rate_pct":50}}}]}}

class NewsHistoryTests(unittest.TestCase):
    def test_first_append(self):
        self.assertTrue(record(report(),[],WHEN)["appended"])
    def test_hash_dedup(self):
        first=record(report(),[],WHEN)
        second=record(report(),first["history"],WHEN)
        self.assertFalse(second["appended"])
        self.assertEqual(len(second["history"]),1)
    def test_second_record(self):
        first=record(report(),[],WHEN)
        second=record(report(2),first["history"],WHEN)
        self.assertEqual(len(second["history"]),2)
    def test_change(self):
        first=record(report(),[],WHEN)
        second=record(report(2),first["history"],WHEN)
        self.assertEqual(second["comparison"]["descriptive_changes_only"][0]["mean_return_change_percentage_points"],1)
    def test_not_verified_comparable(self):
        first=record(report(),[],WHEN)
        second=record(report(2),first["history"],WHEN)
        self.assertFalse(second["comparison"]["comparable"])
    def test_need_two(self):
        self.assertEqual(compare([])["reason"],"NEED_TWO_DISTINCT_REPORTS")
    def test_timezone_required(self):
        with self.assertRaisesRegex(ValueError,"INVALID_RECORDED_AT"):
            record(report(),[],"2026-10-24T09:00:00")
    def test_invalid_version(self):
        with self.assertRaisesRegex(ValueError,"INVALID_V132_REPORT"):
            summarize({"version":"V131.0"})
    def test_duplicate_category(self):
        r=report()
        r["impact"]["categories"].append(r["impact"]["categories"][0])
        with self.assertRaisesRegex(ValueError,"DUPLICATE_CATEGORY"):
            summarize(r)
    def test_no_orders(self):
        r=record(report(),[],WHEN)
        self.assertEqual(r["orders_submitted_to_exchange"],0)
        self.assertFalse(r["live_trading_approved"])
    def test_invalid_label(self):
        with self.assertRaisesRegex(ValueError,"INVALID_LABEL"):
            record(report(),[],WHEN,"x"*121)
    def test_deterministic(self):
        self.assertEqual(record(report(),[],WHEN),record(report(),[],WHEN))

if __name__=="__main__":
    unittest.main()
