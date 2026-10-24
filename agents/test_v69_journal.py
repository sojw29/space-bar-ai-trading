import json
import tempfile
import unittest
from pathlib import Path
from research_journal_v69 import append_run, read_journal, verify

def seed(root, status="CONSISTENT_BUNDLE"):
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / "manifest.json"
    health = root / "health.json"
    manifest.write_text(json.dumps({"version": "V68.0", "status": status,
                                    "live_trading_approved": False}))
    health.write_text(json.dumps({"version": "V66.0", "status": "REVIEW",
                                  "live_trading_approved": False}))
    return manifest, health

class JournalTests(unittest.TestCase):
    def test_two_entries_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, health = seed(root)
            path = root / "runs.jsonl"
            first = append_run(path, manifest, health)
            second = append_run(path, manifest, health)
            self.assertEqual(first["sequence"], 1)
            self.assertEqual(second["previous_hash"], first["entry_hash"])
            self.assertTrue(verify(read_journal(path)))

    def test_tampering_blocks_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, health = seed(root)
            path = root / "runs.jsonl"
            append_run(path, manifest, health)
            entries = read_journal(path)
            entries[0]["status"] = "RESEARCH_DATA_CHECKS_PASS"
            path.write_text(json.dumps(entries[0]) + "\n")
            with self.assertRaisesRegex(ValueError, "JOURNAL_CHAIN_INVALID"):
                append_run(path, manifest, health)

    def test_manifest_failure_records_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, health = seed(root, "BLOCKED")
            result = append_run(root / "runs.jsonl", manifest, health)
            self.assertEqual(result["status"], "BLOCKED")

    def test_missing_report_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "REPORTS_MISSING_OR_INVALID"):
                append_run(root / "runs.jsonl", root / "no.json", root / "missing.json")

    def test_live_approval_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, health = seed(root)
            health.write_text(json.dumps({"version": "V66.0", "status": "REVIEW",
                                          "live_trading_approved": True}))
            with self.assertRaisesRegex(ValueError, "UNSAFE_REPORT"):
                append_run(root / "runs.jsonl", manifest, health)

if __name__ == "__main__":
    unittest.main()
