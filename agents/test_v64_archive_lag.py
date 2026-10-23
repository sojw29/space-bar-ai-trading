import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from archive_lag_v64 import diagnose_file

NOW = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
EXPECTED = int(datetime(2026, 10, 19, 23, 55, tzinfo=timezone.utc).timestamp())

class ArchiveLagTests(unittest.TestCase):
    def write(self, root, timestamps):
        path = Path(root) / "BTC_5m.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "open"])
            for ts in timestamps:
                writer.writerow([ts, 1])
        return path

    def test_expected_publication_delay_is_not_stale(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.write(root, [EXPECTED])
            self.assertEqual(diagnose_file(path, 5, NOW)["status"], "ON_EXPECTED_ARCHIVE_CUTOFF")

    def test_lag_reports_missing_bars(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.write(root, [EXPECTED - 600])
            result = diagnose_file(path, 5, NOW)
            self.assertEqual(result["missing_bars_after_observed"], 2)
            self.assertIn("ARCHIVE_COVERAGE_LAG", result["reasons"])

    def test_missing_file_is_error(self):
        result = diagnose_file(Path("/not/a/real/history.csv"), 5, NOW)
        self.assertEqual(result["status"], "ERROR")

    def test_non_monotonic_is_error(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.write(root, [EXPECTED, EXPECTED - 300])
            self.assertEqual(diagnose_file(path, 5, NOW)["status"], "ERROR")

    def test_future_candle_is_warning(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.write(root, [EXPECTED + 300])
            self.assertIn("NEWER_THAN_ARCHIVE_CUTOFF", diagnose_file(path, 5, NOW)["reasons"])

if __name__ == "__main__":
    unittest.main()
