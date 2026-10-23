import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from data_quality_v65 import score_file

NOW = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
LAST = int(datetime(2026, 10, 19, 23, 55, tzinfo=timezone.utc).timestamp())

class QualityTests(unittest.TestCase):
    def make(self, root, rows):
        path = Path(root) / "BTC_5m.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            writer.writerows(rows)
        return path

    def row(self, stamp, high=2, volume=1):
        return [stamp, 1, high, 0.5, 1.5, volume]

    def test_complete_series_passes(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, [self.row(LAST-300), self.row(LAST)])
            self.assertEqual(score_file(p, 5, NOW)["status"], "PASS")

    def test_gap_requires_review(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, [self.row(LAST-600), self.row(LAST)])
            r = score_file(p, 5, NOW)
            self.assertEqual(r["status"], "REVIEW")
            self.assertEqual(r["missing_internal_bars"], 1)

    def test_invalid_ohlc_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, [self.row(LAST-300), self.row(LAST, high=1)])
            self.assertEqual(score_file(p, 5, NOW)["status"], "FAIL")

    def test_duplicate_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, [self.row(LAST), self.row(LAST)])
            self.assertEqual(score_file(p, 5, NOW)["status"], "FAIL")

    def test_missing_file_fails(self):
        self.assertEqual(score_file(Path("/missing/v65.csv"), 5, NOW)["status"], "FAIL")

if __name__ == "__main__":
    unittest.main()
