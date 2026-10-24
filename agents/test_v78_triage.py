import json
import tempfile
import unittest
from pathlib import Path
from diagnostic_triage_v78 import triage

def event(status, blockers=None, warnings=None):
    return {"version": "V76.0", "recorded_utc": "2026-10-24T00:00:00+00:00",
            "status": status, "environment_status": "ENVIRONMENT_READY",
            "research_status": "OBSERVATION_READY", "blocker_codes": blockers or [],
            "warning_codes": warnings or [], "live_trading_approved": False}

def write(root, events):
    path = root / "events.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    return path

class TriageTests(unittest.TestCase):
    def test_high_before_medium(self):
        with tempfile.TemporaryDirectory() as d:
            path = write(Path(d), [event("BLOCKED", ["RESEARCH_BLOCKED"], ["ENVIRONMENT_REVIEW"])])
            result = triage(path)
            self.assertEqual(result["priorities"][0]["severity"], "HIGH")
            self.assertFalse(result["automatic_repair"])

    def test_frequency_ranking(self):
        with tempfile.TemporaryDirectory() as d:
            path = write(Path(d), [event("BLOCKED", ["RESEARCH_BLOCKED"]),
                                   event("BLOCKED", ["RESEARCH_BLOCKED", "ENVIRONMENT_BLOCKED"])])
            result = triage(path)
            self.assertEqual(result["priorities"][0]["code"], "RESEARCH_BLOCKED")
            self.assertEqual(result["priorities"][0]["count"], 2)

    def test_unknown_code_manual_review(self):
        with tempfile.TemporaryDirectory() as d:
            path = write(Path(d), [event("BLOCKED", ["UNRECOGNIZED_CODE"])])
            result = triage(path)
            self.assertEqual(result["priorities"][0]["severity"], "LOW")

    def test_no_issues(self):
        with tempfile.TemporaryDirectory() as d:
            path = write(Path(d), [event("LOCAL_DIAGNOSTICS_PASS")])
            self.assertEqual(triage(path)["status"], "NO_RECORDED_ISSUES")

    def test_missing_log_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(triage(Path(d) / "missing")["status"], "INSUFFICIENT_DATA")

    def test_corrupt_log_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path = write(Path(d), [event("REVIEW")])
            path.write_text(path.read_text() + "{")
            self.assertEqual(triage(path)["status"], "INSUFFICIENT_DATA")

if __name__ == "__main__":
    unittest.main()
