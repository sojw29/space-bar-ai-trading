import csv
import tempfile
import unittest
from pathlib import Path
from walkforward_v109 import run, folds, _read

class WalkforwardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"history.csv"

    def write(self, n=480):
        with self.path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp","open","high","low","close","volume"])
            for i in range(n):
                price = 100 + 0.02*i + (3 if (i//20)%2 else -3)
                writer.writerow([1700000000000+i*300000,price,price+1,price-1,
                                 price,150 if i%17==0 else 100])

    def test_expanding_folds(self):
        self.write()
        windows = folds(_read(self.path))
        self.assertEqual(len(windows), 4)
        self.assertEqual([len(x[0]) for x in windows], [160,240,320,400])
        self.assertEqual([len(x[1]) for x in windows], [80]*4)
        for train, validation in windows:
            self.assertLess(int(train[-1]["timestamp"]), int(validation[0]["timestamp"]))

    def test_pipeline(self):
        self.write()
        report = run(self.path)
        self.assertEqual(len(report["results"]), 3)
        self.assertEqual(report["results"][0]["validation_folds"], 4)
        self.assertFalse(report["live_trading_approved"])

    def test_deterministic(self):
        self.write()
        self.assertEqual(run(self.path), run(self.path))

    def test_small_data_rejected(self):
        self.write(200)
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_FOLD_DATA"):
            run(self.path)

    def test_duplicate_timestamp_rejected(self):
        self.write()
        lines = self.path.read_text().splitlines()
        lines[3] = lines[2]
        self.path.write_text("\n".join(lines)+"\n")
        with self.assertRaisesRegex(ValueError, "NON_MONOTONIC"):
            run(self.path)

    def test_invalid_fold_size_rejected(self):
        self.write()
        with self.assertRaisesRegex(ValueError, "INVALID_FOLD_SIZES"):
            run(self.path, train_size=50)

if __name__ == "__main__":
    unittest.main()
