import csv
import tempfile
import unittest
from pathlib import Path
from ema_signal_pipeline_v116 import generate, read_history, run

def sample(n=120):
    rows = []
    for i in range(n):
        price = 100 + (i if i<60 else 120-i)*0.4
        rows.append({"timestamp":str(1700000000000+i*300000),
                     "open":str(price),"high":str(price+1),
                     "low":str(price-1),"close":str(price),"volume":"100"})
    return rows

class EmaSignalPipelineTests(unittest.TestCase):
    def test_warmup_has_no_signals(self):
        signals = generate(sample())
        self.assertTrue(all(x["signal"]=="HOLD" for x in signals[:50]))

    def test_crossovers_emitted(self):
        signals = generate(sample())
        self.assertTrue(any(x["signal"]=="SELL" for x in signals))

    def test_completed_bar_signal_never_fills_same_bar(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"history.csv"
            self._write(path, sample())
            result = run(path)
            for fill in result["paper_replay"]["hypothetical_fills"]:
                self.assertEqual(fill["fill_bar_index"], fill["signal_bar_index"]+1)

    def test_deterministic(self):
        self.assertEqual(generate(sample()), generate(sample()))

    def test_reject_short_history(self):
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_EMA_HISTORY"):
            generate(sample(51))

    def test_no_exchange_orders(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"history.csv"
            self._write(path, sample())
            result = run(path)
            self.assertEqual(result["orders_submitted_to_exchange"],0)
            self.assertFalse(result["live_trading_approved"])

    def test_duplicate_timestamp_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"history.csv"
            rows = sample()
            rows[5]["timestamp"] = rows[4]["timestamp"]
            self._write(path, rows)
            with self.assertRaisesRegex(ValueError,"NON_MONOTONIC_TIMESTAMP"):
                read_history(path)

    def test_reject_bad_ohlcv(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"history.csv"
            rows = sample()
            rows[4]["close"] = "nan"
            self._write(path, rows)
            with self.assertRaisesRegex(ValueError,"INVALID_OHLCV"):
                read_history(path)

    @staticmethod
    def _write(path, rows):
        with path.open("w",newline="",encoding="utf-8") as f:
            writer = csv.DictWriter(f,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

if __name__ == "__main__":
    unittest.main()
