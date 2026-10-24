import json
import tempfile
import unittest
from pathlib import Path
from status_timeline_v85 import timeline

def event(time, status, blockers=None, warnings=None):
    return {"version": "V76.0", "recorded_utc": time, "status": status,
            "blocker_codes": blockers or [], "warning_codes": warnings or [],
            "research_only": True, "live_trading_approved": False}

class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "history.jsonl"

    def write(self, events):
        self.path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")

    def test_missing_log_review(self):
        result = timeline(self.path)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["events"], [])

    def test_status_transitions(self):
        self.write([event("2026-10-24T00:00:00+00:00", "BLOCKED", ["RESEARCH_BLOCKED"]),
                    event("2026-10-24T01:00:00+00:00", "REVIEW"),
                    event("2026-10-24T02:00:00+00:00", "LOCAL_DIAGNOSTICS_PASS")])
        result = timeline(self.path)
        self.assertEqual(result["status"], "ANALYZED")
        self.assertEqual(len(result["transitions"]), 2)
        self.assertEqual(result["transitions"][0]["from"], "BLOCKED")
        self.assertEqual(result["transitions"][1]["to"], "LOCAL_DIAGNOSTICS_PASS")
        self.assertFalse(result["live_trading_approved"])

    def test_unchanged_status_has_no_transitions(self):
        self.write([event("2026-10-24T00:00:00+00:00", "BLOCKED"),
                    event("2026-10-24T01:00:00+00:00", "BLOCKED")])
        self.assertEqual(timeline(self.path)["transitions"], [])

    def test_recent_window(self):
        self.write([event(f"2026-10-24T0{i}:00:00+00:00", "BLOCKED") for i in range(4)])
        self.assertEqual(len(timeline(self.path, recent=2)["events"]), 2)

    def test_invalid_event_fails_closed(self):
        self.path.write_text('{"version":"V76.0"}\n', encoding="utf-8")
        result = timeline(self.path)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["events"], [])

    def test_invalid_recent_limit(self):
        with self.assertRaises(ValueError):
            timeline(self.path, recent=0)

if __name__ == "__main__":
    unittest.main()
