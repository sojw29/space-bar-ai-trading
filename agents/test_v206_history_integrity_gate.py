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
            self.rows.append({"timestamp":1700000000000+i*300000,"open":p,
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
