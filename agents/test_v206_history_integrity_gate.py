"""V206 strict offline history integrity tests."""
import csv
import tempfile
import unittest
from pathlib import Path

from history_integrity_gate_v206 import inspect_history
from publish_scorecard_v203 import publish


class HistoryGateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"BTC_5m.csv"
        self.rows=[]
        for i in range(600):
            p=100+i*.02
            self.rows.append({"timestamp":1700000100000+i*300000,"open":p,
                              "high":p+1,"low":p-1,"close":p,"volume":100})
        self.write()

    def write(self):
        with self.path.open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=["timestamp","open","high","low","close","volume"])
            writer.writeheader()
            writer.writerows(self.rows)

    def test_valid_history(self):
        result=inspect_history(self.path)
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(result["missing_candles"],0)
        self.assertFalse(result["orders_allowed"])

    def test_full_year_one_minute_history_is_accepted(self):
        # The collector emits 525,600 1m candles for 365 days; 500k was too low.
        minute_path = Path(self.temp.name) / "BTC_1m.csv"
        with minute_path.open("w", encoding="utf-8", newline="") as stream:
            stream.write("timestamp,open,high,low,close,volume\\n".replace("\\n", "\n"))
            for i in range(365 * 24 * 60):
                stream.write(f"{1700000100000 + i * 60000},100,101,99,100,1\\n".replace("\\n", "\n"))
        result = inspect_history(minute_path, timeframe="1m")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["candles"], 525600)
        self.assertEqual(result["missing_candles"], 0)

    def test_collector_seconds_pass_and_publish(self):
        # agents/history.py saves epoch seconds, not milliseconds.
        for row in self.rows:
            row["timestamp"] //= 1000
        self.write()
        integrity = inspect_history(self.path)
        self.assertEqual(integrity["status"], "PASS")
        self.assertEqual(integrity["timestamp_unit"], "seconds")
        self.assertEqual(integrity["missing_candles"], 0)
        target = Path(self.temp.name) / "collector_snapshot.json"
        self.assertEqual(publish(self.path, target)["status"],
                         "OFFLINE_SNAPSHOT_PUBLISHED")
        self.assertTrue(target.is_file())

    def test_mixed_seconds_and_milliseconds_blocked(self):
        self.rows[10]["timestamp"] //= 1000
        self.write()
        result = inspect_history(self.path)
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["errors"][0]["reason"], "MIXED_TIMESTAMP_UNITS")

    def test_off_grid_seconds_blocked(self):
        for row in self.rows:
            row["timestamp"] = row["timestamp"] // 1000 + 1
        self.write()
        result = inspect_history(self.path)
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["errors"][0]["reason"], "MISALIGNED_TIMESTAMP")

    def test_microsecond_timestamps_blocked(self):
        self.rows[10]["timestamp"] *= 1000
        self.write()
        result = inspect_history(self.path)
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["errors"][0]["reason"], "INVALID_TIMESTAMP_UNIT")

    def test_uniformly_shifted_candles_blocked_and_not_published(self):
        # Equal 5m deltas alone must not admit timestamps shifted off the UTC grid.
        for row in self.rows:
            row["timestamp"] += 1
        self.write()
        result = inspect_history(self.path)
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["errors"][0]["reason"], "MISALIGNED_TIMESTAMP")
        target = Path(self.temp.name) / "shifted_snapshot.json"
        with self.assertRaisesRegex(ValueError, "HISTORY_INTEGRITY_BLOCKED"):
            publish(self.path, target)
        self.assertFalse(target.exists())

    def test_duplicate_blocked(self):
        self.rows[12]["timestamp"]=self.rows[11]["timestamp"]
        self.write()
        self.assertEqual(inspect_history(self.path)["status"],"BLOCK")

    def test_missing_candle_blocked_and_no_publish(self):
        for row in self.rows[30:]:
            row["timestamp"]+=300000
        self.write()
        self.assertEqual(inspect_history(self.path)["status"],"BLOCK")
        target=Path(self.temp.name)/"snapshot.json"
        with self.assertRaisesRegex(ValueError,"HISTORY_INTEGRITY_BLOCKED"):
            publish(self.path,target)
        self.assertFalse(target.exists())

    def test_invalid_ohlc_blocked(self):
        self.rows[10]["high"]=0
        self.write()
        self.assertEqual(inspect_history(self.path)["status"],"BLOCK")


if __name__=="__main__":
    unittest.main()
