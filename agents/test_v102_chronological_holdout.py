import csv
import tempfile
import unittest
from pathlib import Path
from chronological_holdout_v102 import split_csv, COLUMNS

class ChronologicalHoldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input.csv"
        self.train = self.root / "train.csv"
        self.valid = self.root / "validation.csv"

    def write(self, rows):
        with self.source.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def rows(self, n=100):
        return [{"timestamp": str(1_700_000_000_000 + i*60_000),
                 "open": "10", "high": "12", "low": "9",
                 "close": "11", "volume": "100"} for i in range(n)]

    def test_ordered_split_and_disjoint_boundary(self):
        self.write(self.rows())
        result = split_csv(self.source, self.train, self.valid)
        self.assertEqual((result["train_rows"], result["validation_rows"]), (70, 30))
        with self.train.open(newline="") as f:
            training = list(csv.DictReader(f))
        with self.valid.open(newline="") as f:
            validation = list(csv.DictReader(f))
        self.assertLess(int(training[-1]["timestamp"]), int(validation[0]["timestamp"]))
        self.assertEqual(len(training)+len(validation), 100)

    def test_unsorted_data_rejected(self):
        rows = self.rows()
        rows[50], rows[51] = rows[51], rows[50]
        self.write(rows)
        with self.assertRaisesRegex(ValueError, "NON_MONOTONIC"):
            split_csv(self.source, self.train, self.valid)

    def test_duplicate_timestamp_rejected(self):
        rows = self.rows()
        rows[10]["timestamp"] = rows[9]["timestamp"]
        self.write(rows)
        with self.assertRaises(ValueError):
            split_csv(self.source, self.train, self.valid)

    def test_invalid_candle_rejected(self):
        rows = self.rows()
        rows[10]["high"] = "5"
        self.write(rows)
        with self.assertRaisesRegex(ValueError, "INVALID_CANDLE_RANGE"):
            split_csv(self.source, self.train, self.valid)

    def test_small_sample_rejected(self):
        self.write(self.rows(40))
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_ROWS"):
            split_csv(self.source, self.train, self.valid)

    def test_no_overwrite(self):
        self.write(self.rows())
        self.train.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "OUTPUT_EXISTS"):
            split_csv(self.source, self.train, self.valid)

    def test_reject_overlapping_paths(self):
        self.write(self.rows())
        with self.assertRaisesRegex(ValueError, "OVERLAPPING_PATHS"):
            split_csv(self.source, self.source, self.valid)

    def test_reject_nonfinite_price(self):
        rows = self.rows()
        rows[1]["close"] = "nan"
        self.write(rows)
        with self.assertRaisesRegex(ValueError, "INVALID_OHLCV"):
            split_csv(self.source, self.train, self.valid)

if __name__ == "__main__":
    unittest.main()
