"""V212 ex-post regime strategy attribution tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from regime_strategy_attribution_v212 import assess_regime_strategy_performance
from publish_scorecard_v203 import publish


class AttributionTests(unittest.TestCase):
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

    def test_four_nonoverlapping_windows_and_nine_groups(self):
        result=assess_regime_strategy_performance(self.source)
        self.assertEqual(result["status"],"DESCRIPTIVE_ONLY")
        self.assertEqual(len(result["windows"]),4)
        self.assertEqual(len(result["summary"]),9)
        self.assertEqual(sum(row["windows"] for row in result["summary"]),12)
        self.assertEqual(result["unclassified_tail_candles"],0)
        self.assertFalse(result["strategy_selection_enabled"])

    def test_insufficient_data_explicitly_marked(self):
        short=Path(self.tmp.name)/"short.csv"
        with self.source.open(encoding="utf-8") as src, short.open("w",encoding="utf-8") as dst:
            for index,line in enumerate(src):
                if index>280: break
                dst.write(line)
        result=assess_regime_strategy_performance(short)
        self.assertEqual(result["status"],"INSUFFICIENT_HOLDOUT_CANDLES")
        self.assertEqual(result["windows"],[])

    def test_publish_attaches_attribution(self):
        output=Path(self.tmp.name)/"report.json"
        publish(self.source,output)
        report=json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["regime_strategy_attribution"]["version"],"V212.0")
        self.assertFalse(report["regime_strategy_attribution"]["orders_allowed"])


if __name__=="__main__":
    unittest.main()
