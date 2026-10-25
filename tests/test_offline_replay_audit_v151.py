import csv
import tempfile
import unittest
from pathlib import Path
from agents.offline_replay_audit_v151 import audit_history, report_json


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "BTC_1m.csv"
        with self.path.open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
            writer.writerows([
                (60000, 100, 101, 99, 100, 1000),
                (120000, 100, 111, 99, 110, 1000),
                (180000, 110, 121, 109, 120, 1000),
            ])

    def tearDown(self):
        self.folder.cleanup()

    def test_deterministic_report(self):
        a = audit_history(self.path, symbol="BTC", timeframe_minutes=1,
                          actions={0: ("BUY", 1), 1: ("SELL", 1)})
        b = audit_history(self.path, symbol="BTC", timeframe_minutes=1,
                          actions={0: ("BUY", 1), 1: ("SELL", 1)})
        self.assertEqual(report_json(a), report_json(b))
        self.assertEqual(a.closed_trades, 1)
        self.assertGreater(a.realized_pnl, 0)
        self.assertEqual(a.open_quantity, 0)

    def test_no_actions_not_fake_trades(self):
        a = audit_history(self.path, symbol="BTC", timeframe_minutes=1)
        self.assertEqual(a.closed_trades, 0)
        self.assertEqual(a.ending_realized_equity, 10000)

    def test_missing_data_rejected(self):
        with self.path.open("a") as file:
            file.write("300000,120,121,119,120,1000\n")
        with self.assertRaises(ValueError):
            audit_history(self.path, symbol="BTC", timeframe_minutes=1)

    def test_invalid_symbol_rejected(self):
        with self.assertRaises(ValueError):
            audit_history(self.path, symbol="DOGE", timeframe_minutes=1)

    def test_invalid_timeframe_rejected(self):
        with self.assertRaises(ValueError):
            audit_history(self.path, symbol="BTC", timeframe_minutes=2)


if __name__ == "__main__":
    unittest.main()
