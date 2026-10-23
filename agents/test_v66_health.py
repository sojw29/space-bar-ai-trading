import unittest
from research_health_v66 import aggregate

def fixtures():
    v63 = {"version": "V63.0", "status": "OBSERVATION_ONLY", "errors": []}
    rows64 = []
    rows65 = []
    for coin in ("BTC", "ETH", "SOL"):
        for tf in (1, 5, 15):
            base = {"path": f"data/history/{coin}_{tf}m.csv", "timeframe_minutes": tf}
            rows64.append(dict(base, status="ON_EXPECTED_ARCHIVE_CUTOFF"))
            rows65.append(dict(base, status="PASS"))
    return v63, {"version": "V64.0", "results": rows64}, {"version": "V65.0", "results": rows65}

class HealthTests(unittest.TestCase):
    def test_valid_data_only(self):
        result = aggregate(*fixtures())
        self.assertEqual(result["status"], "RESEARCH_DATA_CHECKS_PASS")
        self.assertFalse(result["live_trading_approved"])

    def test_missing_report_blocks(self):
        a, b, c = fixtures()
        self.assertEqual(aggregate(a, b, None)["status"], "BLOCKED")

    def test_incomplete_datasets_block(self):
        a, b, c = fixtures()
        c["results"].pop()
        self.assertEqual(aggregate(a, b, c)["status"], "BLOCKED")

    def test_integrity_failure_blocks(self):
        a, b, c = fixtures()
        a["errors"] = ["BAD"]
        self.assertEqual(aggregate(a, b, c)["status"], "BLOCKED")

    def test_review_does_not_pass(self):
        a, b, c = fixtures()
        c["results"][0]["status"] = "REVIEW"
        self.assertEqual(aggregate(a, b, c)["status"], "REVIEW")

    def test_duplicate_key_blocks(self):
        a, b, c = fixtures()
        c["results"][1] = dict(c["results"][0])
        self.assertEqual(aggregate(a, b, c)["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
