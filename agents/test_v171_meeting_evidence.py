"""V171: meeting provenance is auditable but never trade authorization."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from meeting_quality_report_v166 import build_report


class MeetingEvidenceTests(unittest.TestCase):
    def test_missing_evidence_is_unverified_and_wait(self):
        with tempfile.TemporaryDirectory() as d:
            result = build_report(Path(d) / "absent.json")
            self.assertIsNone(result["evidence"]["sha256"])
            self.assertFalse(result["evidence"]["verified"])
            self.assertEqual(result["agents"]["COMMANDER"]["decision"], "WAIT")
            self.assertFalse(result["orders_enabled"])

    def test_input_bytes_are_fingerprinted(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "quality.json"
            data = {"overall_status": "PASS", "research_usable": True,
                    "results": [{"status": "PASS", "research_usable": True} for _ in range(9)]}
            raw = json.dumps(data).encode("utf-8")
            path.write_bytes(raw)
            result = build_report(path)
            self.assertEqual(result["evidence"]["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(result["evidence"]["bytes"], len(raw))
            self.assertTrue(result["evidence"]["verified"])
            self.assertEqual(result["agents"]["COMMANDER"]["decision"], "WAIT")
            self.assertFalse(result["live_trading_approved"])

    def test_malformed_report_fingerprint_does_not_imply_verification(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "quality.json"
            path.write_text("{broken", encoding="utf-8")
            result = build_report(path)
            self.assertIsNotNone(result["evidence"]["sha256"])
            self.assertFalse(result["evidence"]["verified"])
            self.assertEqual(result["agents"]["GUARDIAN"]["state"], "VETO")


if __name__ == "__main__":
    unittest.main()
