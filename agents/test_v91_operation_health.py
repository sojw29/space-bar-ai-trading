import json
import tempfile
import unittest
from pathlib import Path
from operation_health_v91 import summarize

def event(result="SUCCESS", stamp="2026-10-24T00:00:00+00:00"):
    return {"version": "V90.0", "timestamp_utc": stamp, "operation": "MOBILE_REPORT",
            "result": result, "status": "ERROR" if result == "FAILED" else "BLOCKED" if result == "BLOCKED" else "REVIEW",
            "research_only": True, "live_trading_approved": False}

class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "journal.jsonl"

    def write(self, entries):
        self.path.write_text("".join(json.dumps(x) + "\n" for x in entries), encoding="utf-8")

    def test_missing_review(self):
        self.assertEqual(summarize(self.path)["status"], "REVIEW")

    def test_success(self):
        self.write([event()])
        result = summarize(self.path)
        self.assertEqual(result["status"], "OPERATIONAL")
        self.assertFalse(result["live_trading_approved"])

    def test_failure_streak(self):
        self.write([event("SUCCESS"), event("FAILED", "2026-10-24T01:00:00+00:00"),
                    event("FAILED", "2026-10-24T02:00:00+00:00")])
        result = summarize(self.path)
        self.assertEqual(result["consecutive_failures"], 2)
        self.assertEqual(result["status"], "BLOCKED")

    def test_blocked_result(self):
        self.write([event("BLOCKED")])
        self.assertEqual(summarize(self.path)["status"], "BLOCKED")

    def test_invalid_event(self):
        bad = event()
        bad["secret"] = "unexpected"
        self.write([bad])
        self.assertEqual(summarize(self.path)["status"], "REVIEW")

    def test_out_of_order(self):
        self.write([event(stamp="2026-10-24T02:00:00+00:00"),
                    event(stamp="2026-10-24T01:00:00+00:00")])
        self.assertEqual(summarize(self.path)["status"], "REVIEW")

    def test_limit(self):
        self.write([event("FAILED"), event("SUCCESS", "2026-10-24T01:00:00+00:00")])
        self.assertEqual(summarize(self.path, limit=1)["total"], 1)

    def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            summarize(self.path, limit=0)

if __name__ == "__main__":
    unittest.main()
