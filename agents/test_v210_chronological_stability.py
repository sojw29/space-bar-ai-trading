"""V210 chronological holdout stability tests."""
import csv
import tempfile
import unittest
from pathlib import Path
from chronological_stability_v210 import assess_stability
from publish_scorecard_v203 import publish
import json


class StabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source=Path(self.tmp.name)/"BTC_5m.csv"
        with self.source.open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=["timestamp","open","high","low","close","volume"])
            writer.writeheader()
            for i in range(1200):
                p=100+i*.02+(5 if (i//25)%2 else -5)
                writer.writerow({"timestamp":1700000100+i*300,"open":p,
                                 "high":p+1,"low":p-1,"close":p,
                                 "volume":150 if i%17==0 else 80})

    def test_three_chronological_slices(self):
        report=assess_stability(self.source)
        self.assertEqual(report["status"],"DESCRIPTIVE_STABILITY_ONLY")
        self.assertEqual(len(report["rows"]),3)
        for row in report["rows"]:
            self.assertEqual(len(row["slices"]),3)
            self.assertTrue(all(s["candles"]>=80 for s in row["slices"]))
            self.assertEqual(sum(s["candles"] for s in row["slices"]),360)
        self.assertFalse(report["orders_allowed"])

    def test_insufficient_validation_candles_fail_closed(self):
        short=Path(self.tmp.name)/"short.csv"
        with self.source.open(encoding="utf-8") as src,short.open("w",encoding="utf-8") as dst:
            for index,line in enumerate(src):
                if index>600: break
                dst.write(line)
        report=assess_stability(short)
        self.assertEqual(report["status"],"INSUFFICIENT_HOLDOUT_CANDLES")
        self.assertEqual(report["rows"],[])

    def test_publish_attaches_stability(self):
        output=Path(self.tmp.name)/"result.json"
        publish(self.source,output)
        report=json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["chronological_stability"]["version"],"V210.0")


if __name__=="__main__":
    unittest.main()
