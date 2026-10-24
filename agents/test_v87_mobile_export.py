import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from mobile_status_export_v87 import create_payload, export

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)

def sample(status="REVIEW"):
    return {"status": status,
            "current": {"pc_status": "REVIEW", "audit_status": status},
            "timeline": {"status": "ANALYZED",
                         "events": [{"timestamp_utc": "2026-10-24T00:00:00+00:00",
                                     "status": "BLOCKED", "blocker_codes": ["SECRET"],
                                     "warning_codes": []}],
                         "transitions": [{"timestamp_utc": "2026-10-24T00:00:00+00:00",
                                          "from": "BLOCKED", "to": "REVIEW"}]}}

class MobileExportTests(unittest.TestCase):
    @patch("mobile_status_export_v87.dashboard_data", return_value=sample())
    def test_sanitized_payload(self, _):
        data = create_payload(now=NOW)
        raw = json.dumps(data)
        self.assertNotIn("SECRET", raw)
        self.assertNotIn("blocker_codes", raw)
        self.assertEqual(data["transport"], "LOCAL_FILE_ONLY")
        self.assertFalse(data["live_trading_approved"])

    @patch("mobile_status_export_v87.dashboard_data", return_value=sample())
    def test_atomic_export(self, _):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "status.json"
            export(path, now=NOW)
            self.assertEqual(json.loads(path.read_text())["schema"], "spacebar.local-status.v87")

    @patch("mobile_status_export_v87.dashboard_data", return_value=sample("UNKNOWN"))
    def test_unknown_status_fails_closed(self, _):
        self.assertEqual(create_payload(now=NOW)["overall_status"], "REVIEW")

    @patch("mobile_status_export_v87.dashboard_data", return_value=sample("BLOCKED"))
    def test_blocked_preserved(self, _):
        self.assertEqual(create_payload(now=NOW)["overall_status"], "BLOCKED")

    def test_real_empty_repo(self):
        with tempfile.TemporaryDirectory() as d:
            data = create_payload(repo=Path(d), now=NOW)
            self.assertEqual(data["overall_status"], "BLOCKED")
            self.assertFalse(data["live_trading_approved"])

if __name__ == "__main__":
    unittest.main()
