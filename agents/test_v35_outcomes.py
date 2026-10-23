"""V35 post-hoc checks: missing future bars, WAIT, direction and no ledger writes."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_events_v27 as ev
import decision_ledger_v34 as ledger
import outcomes_v35 as v35


def candles():
    data = []
    for i in range(60):
        p = 100 + i * .1
        data.append({"timestamp": 1700000100 + i*300, "open":p-.01,
                     "high":p+.1, "low":p-.1, "close":p, "volume":20})
    return data


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.sqlite3"
        self.envelope = ev.analyze_and_emit(candles())
        ledger.record(self.db, self.envelope)
        self.entry = ledger.read_recent(self.db)
        ts = v35._timestamp(self.envelope["observed_candle_utc"])
        self.ts = ts
        self.history = {ts: 100.0, ts+300: 101.0, ts+600: 102.0,
                        ts+900: 103.0}

    def tearDown(self):
        self.tmp.cleanup()

    def test_horizons_require_observed_future(self):
        report = v35.evaluate(self.entry, self.history)[0]
        self.assertEqual(report["source"], "HISTORICAL_POSTHOC")
        self.assertFalse(report["independent_oos_verified"])
        self.assertFalse(report["trading_result"])
        self.assertEqual(report["outcomes"][0]["raw_close_change_pct"], 1.0)
        self.assertEqual(report["outcomes"][1]["raw_close_change_pct"], 3.0)
        self.assertIsNone(report["outcomes"][2]["raw_close_change_pct"])

    def test_missing_intermediate_candle_blocks_observation(self):
        history = dict(self.history)
        del history[self.ts+600]
        result = v35.evaluate(self.entry, history, horizons=(3,))[0]["outcomes"][0]
        self.assertEqual(result["status"], "INSUFFICIENT_FUTURE_CANDLES")

    def test_wait_has_no_direction_score(self):
        report = v35.evaluate(self.entry, self.history, horizons=(1,))[0]
        # Directly make a valid WAIT consensus snapshot via empty/flat candles.
        flat = candles()
        for row in flat:
            row.update(open=100, high=100, low=100, close=100)
        waiting = ev.analyze_and_emit(flat)
        entry = copy.deepcopy(self.entry[0])
        entry["event_envelope"] = waiting
        self.assertEqual(v35.evaluate([entry], self.history, horizons=(1,))[0]
                         ["outcomes"][0]["direction_match"], None)

    def test_ledger_unchanged(self):
        before = ledger.read_recent(self.db)
        v35.evaluate(self.entry, self.history)
        self.assertEqual(before, ledger.read_recent(self.db))

    def test_bad_horizon_rejected(self):
        with self.assertRaises(ValueError):
            v35.evaluate(self.entry, self.history, horizons=(0,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
