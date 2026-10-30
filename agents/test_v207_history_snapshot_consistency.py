"""V207 history mutation fails closed and preserves last published snapshot."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import publish_scorecard_v203 as publisher


class ConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "BTC_5m.csv"
        self.target = Path(self.tmp.name) / "snapshot.json"
        with self.source.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp","open","high","low","close","volume"])
            writer.writeheader()
            for i in range(600):
                price=100+i*.02+(5 if (i//25)%2 else -5)
                writer.writerow({"timestamp":1700000100+i*300,
                    "open":price,"high":price+1,"low":price-1,"close":price,
                    "volume":150 if i%17==0 else 80})
        self.target.write_text('{"previous":"intact"}', encoding="utf-8")

    def test_change_after_integrity_blocks_before_backtest(self):
        original=publisher._sha256_file
        counter=[0]
        def changing(path):
            counter[0]+=1
            if counter[0]==2:
                with self.source.open("a",encoding="utf-8") as stream:
                    stream.write("\n")
            return original(path)
        with patch.object(publisher,"_sha256_file",side_effect=changing):
            with self.assertRaisesRegex(ValueError,"HISTORY_CHANGED_DURING_VALIDATION"):
                publisher.publish(self.source,self.target)
        self.assertEqual(self.target.read_text(encoding="utf-8"),'{"previous":"intact"}')

    def test_change_during_backtest_blocks_publish(self):
        from multi_strategy_holdout_v105 import run as actual_run
        def mutated(*args,**kwargs):
            result=actual_run(*args,**kwargs)
            with self.source.open("a",encoding="utf-8") as stream:
                stream.write("\n")
            return result
        with patch.object(publisher,"run",side_effect=mutated):
            with self.assertRaisesRegex(ValueError,"HISTORY_CHANGED_DURING_BACKTEST"):
                publisher.publish(self.source,self.target)
        self.assertEqual(self.target.read_text(encoding="utf-8"),'{"previous":"intact"}')

    def test_stable_source_still_publishes(self):
        summary=publisher.publish(self.source,self.target)
        self.assertEqual(summary["status"],"OFFLINE_SNAPSHOT_PUBLISHED")


if __name__=="__main__":
    unittest.main()
