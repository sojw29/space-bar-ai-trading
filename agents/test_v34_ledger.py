"""V34 immutable SQLite ledger unit tests. No exchange/network access."""
import copy
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_events_v27 as ev
import decision_ledger_v34 as ledger


def candles():
    rows = []
    for i in range(60):
        price = 100 + 0.1 * i
        rows.append({"timestamp": 1700000100 + i * 300, "open": price-0.01,
                     "high": price+0.1, "low": price-0.1, "close": price,
                     "volume": 20})
    return rows


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "reports" / "ledger.sqlite3"
        self.envelope = ev.analyze_and_emit(candles())

    def tearDown(self):
        self.temp.cleanup()

    def test_insert_is_idempotent(self):
        self.assertEqual(ledger.record(self.db, self.envelope), "inserted")
        self.assertEqual(ledger.record(self.db, self.envelope), "unchanged")
        results = ledger.read_recent(self.db)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["event_envelope"], self.envelope)
        self.assertEqual(len(results[0]["sha256"]), 64)

    def test_changed_snapshot_same_candle_refused(self):
        ledger.record(self.db, self.envelope)
        altered = copy.deepcopy(self.envelope)
        altered["events"][0]["reason"] = "changed historical explanation"
        with self.assertRaisesRegex(ValueError, "Immutable ledger conflict"):
            ledger.record(self.db, altered)
        self.assertEqual(len(ledger.read_recent(self.db)), 1)

    def test_rejects_unsafe_and_inconsistent_votes(self):
        for field, value in (("orders_enabled", True),
                             ("live_trading_approved", True),
                             ("independent_oos_verified", True)):
            altered = copy.deepcopy(self.envelope)
            altered[field] = value
            with self.assertRaises(ValueError):
                ledger.record(self.db, altered)
        altered = copy.deepcopy(self.envelope)
        altered["events"][-1]["long_votes"] = 999
        with self.assertRaises(ValueError):
            ledger.record(self.db, altered)

    def test_read_missing_and_limit(self):
        self.assertEqual(ledger.read_recent(self.db), [])
        with self.assertRaises(ValueError):
            ledger.read_recent(self.db, 101)


if __name__ == "__main__":
    unittest.main(verbosity=2)
