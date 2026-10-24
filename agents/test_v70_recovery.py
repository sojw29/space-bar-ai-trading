import json
import tempfile
import unittest
from pathlib import Path
from research_journal_v69 import append_run
from research_recovery_v70 import inspect_journal

def seed(root):
    manifest = root / "manifest.json"
    health = root / "health.json"
    manifest.write_text(json.dumps({"version": "V68.0", "status": "CONSISTENT_BUNDLE",
                                    "live_trading_approved": False}))
    health.write_text(json.dumps({"version": "V66.0", "status": "REVIEW",
                                  "live_trading_approved": False}))
    path = root / "runs.jsonl"
    append_run(path, manifest, health)
    append_run(path, manifest, health)
    return path

class RecoveryTests(unittest.TestCase):
    def test_valid_chain(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspect_journal(seed(Path(d)))
            self.assertEqual(result["status"], "CHAIN_VALID")
            self.assertEqual(result["valid_prefix_entries"], 2)

    def test_truncated_final_line(self):
        with tempfile.TemporaryDirectory() as d:
            path = seed(Path(d))
            lines = path.read_text().splitlines()
            path.write_text(lines[0] + "\n" + '{"sequence":2')
            before = path.read_bytes()
            result = inspect_journal(path)
            self.assertEqual(result["issue"], "INVALID_JSON")
            self.assertEqual(result["valid_prefix_entries"], 1)
            self.assertEqual(result["first_invalid_line"], 2)
            self.assertEqual(path.read_bytes(), before)

    def test_modified_hash(self):
        with tempfile.TemporaryDirectory() as d:
            path = seed(Path(d))
            lines = path.read_text().splitlines()
            item = json.loads(lines[1])
            item["status"] = "BLOCKED"
            path.write_text(lines[0] + "\n" + json.dumps(item) + "\n")
            result = inspect_journal(path)
            self.assertEqual(result["issue"], "ENTRY_HASH_MISMATCH")
            self.assertEqual(result["valid_prefix_entries"], 1)

    def test_missing_journal(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspect_journal(Path(d) / "absent.jsonl")
            self.assertEqual(result["issue"], "JOURNAL_UNREADABLE")

    def test_empty_journal(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "empty.jsonl"
            path.write_text("")
            self.assertEqual(inspect_journal(path)["issue"], "EMPTY_JOURNAL")

    def test_bad_sequence(self):
        with tempfile.TemporaryDirectory() as d:
            path = seed(Path(d))
            lines = path.read_text().splitlines()
            item = json.loads(lines[1])
            item["sequence"] = 99
            path.write_text(lines[0] + "\n" + json.dumps(item) + "\n")
            self.assertEqual(inspect_journal(path)["issue"], "INVALID_SEQUENCE")

if __name__ == "__main__":
    unittest.main()
