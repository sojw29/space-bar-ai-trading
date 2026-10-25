import csv
import tempfile
import unittest
from pathlib import Path
from agents.offline_candle_replay_v150 import load_candles, replay


def rows():
    return [
        (1000, 100, 101, 99, 100, 1000),
        (2000, 100, 111, 99, 110, 1000),
        (3000, 110, 121, 109, 120, 1000),
        (4000, 120, 121, 119, 120, 1000),
    ]


class ReplayTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.csv"
            with path.open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
                writer.writerows(data)
            return load_candles(path, interval_ms=1000)

    def test_next_open_not_signal_close(self):
        candles = self.load(rows())
        s = replay(candles, {0: ("BUY", 1), 1: ("SELL", 1)})
        self.assertEqual(len(s.performance.records), 1)
        self.assertGreater(s.performance.records[0], 9)

    def test_determinism(self):
        candles = self.load(rows())
        actions = {0: ("BUY", 1), 1: ("SELL", 1)}
        self.assertEqual(replay(candles, actions).performance.records,
                         replay(candles, actions).performance.records)

    def test_missing_candle_rejected(self):
        data = rows()
        data[2] = (5000, *data[2][1:])
        with self.assertRaises(ValueError):
            self.load(data)

    def test_invalid_ohlc_rejected(self):
        data = rows()
        data[0] = (1000, 100, 99, 99, 100, 1000)
        with self.assertRaises(ValueError):
            self.load(data)

    def test_capacity_rejects_without_fill(self):
        candles = self.load(rows())
        s = replay(candles, {0: ("BUY", 100)})
        self.assertEqual(s.ledger.signed_qty, 0)
        self.assertEqual(len(s.performance.records), 0)

    def test_no_future_bar_rejected(self):
        candles = self.load(rows())
        with self.assertRaises(ValueError):
            replay(candles, {len(candles)-1: ("BUY", 1)})


if __name__ == "__main__":
    unittest.main()
