"""Offline regression tests for V163 historical OHLCV ingestion."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import history


class HistoryIntegrityTests(unittest.TestCase):
    def test_reject_nonfinite_values(self):
        valid = ["300000", "10", "11", "9", "10", "2"]
        for column in range(1, 6):
            with self.subTest(column=column):
                for value in ("nan", "inf", "-inf"):
                    row = valid.copy()
                    row[column] = value
                    candles = {}
                    history.add_rows(candles, [row], 300, 301)
                    self.assertEqual(candles, {})

    def test_accept_valid_row(self):
        candles = {}
        added = history.add_rows(candles, [["300000", "10", "11", "9", "10", "2"]], 300, 301)
        self.assertEqual(added, 1)
        self.assertTrue(all(math.isfinite(x) for x in candles[300]))


if __name__ == "__main__":
    unittest.main()
