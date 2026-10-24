import json
import tempfile
import unittest
from pathlib import Path
from diagnostic_trends_v77 import analyze

def event(status, blockers=None):
    return {"version": "V76.0", "recorded_utc": "2026-10-24T00:00:00+00:00",
            "status": status, "environment_status": "ENVIRONMENT_READY",
            "research_status": "OBSERVATION_READY", "blocker_codes": blockers or [],
            "warning_codes": [], "live_trading_approved": False}

class TrendTests(unittest.TestCase):
    def test_counts_and_changes(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "log.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in [
                event("BLOCKED", ["RESEARCH_BLOCKED"]), event("REVIEW"),
                event("LOCAL_DIAGNOSTICS_PASS")]) + "\n")
            result = analyze(path)
            self.assertEqual(result["status"], "ANALYZED")
            self.assertEqual(result["status_changes"], 2)
            self.assertEqual(result["counts"]["BLOCKED"], 1)

    def test_missing_log(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(analyze(Path(d) / "absent")["status"], "INSUFFICIENT_DATA")

    def test_corrupt_line_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "log.jsonl"
            path.write_text(json.dumps(event("REVIEW")) + "\n{")
            result = analyze(path)
            self.assertEqual(result["status"], "INSUFFICIENT_DATA")
            self.assertIn("INVALID_EVENT_LINE_2", result["issues"])

    def test_unsafe_live_flag_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "log.jsonl"
            obj = event("REVIEW")
            obj["live_trading_approved"] = True
            path.write_text(json.dumps(obj))
            self.assertNotEqual(analyze(path)["status"], "ANALYZED")

    def test_log_limit(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "log.jsonl"
            path.write_text(json.dumps(event("REVIEW")) + "\n" + json.dumps(event("REVIEW")))
            self.assertIn("LOG_EXCEEDS_LIMIT", analyze(path, limit=1)["issues"])

    def test_invalid_code_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "log.jsonl"
            path.write_text(json.dumps(event("BLOCKED", ["api_key=secret"])))
            self.assertNotEqual(analyze(path)["status"], "ANALYZED")

if __name__ == "__main__":
    unittest.main()
