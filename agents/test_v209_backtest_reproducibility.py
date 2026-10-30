"""V209 identical-run reproducibility gate."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import publish_scorecard_v203 as pub


class ReproducibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source=Path(self.tmp.name)/"BTC_5m.csv"
        self.output=Path(self.tmp.name)/"report.json"
        with self.source.open("w",newline="",encoding="utf-8") as handle:
            writer=csv.DictWriter(handle,fieldnames=["timestamp","open","high","low","close","volume"])
            writer.writeheader()
            for i in range(600):
                p=100+i*.02+(5 if (i//25)%2 else -5)
                writer.writerow({"timestamp":1700000100+i*300,"open":p,
                    "high":p+1,"low":p-1,"close":p,"volume":150 if i%17==0 else 80})

    def test_two_matching_runs_publish_attestation(self):
        summary=pub.publish(self.source,self.output)
        self.assertEqual(summary["status"],"OFFLINE_SNAPSHOT_PUBLISHED")
        report=json.loads(self.output.read_text(encoding="utf-8"))
        check=report["reproducibility_check"]
        self.assertEqual(check["status"],"PASS")
        self.assertEqual(check["runs"],2)
        self.assertEqual(len(check["canonical_result_sha256"]),64)
        self.assertFalse(check["orders_allowed"])

    def test_nondeterministic_result_blocks_and_preserves_previous(self):
        self.output.write_text("previous",encoding="utf-8")
        actual=pub.run
        counter=[0]
        def drift(*args,**kwargs):
            result=actual(*args,**kwargs)
            counter[0]+=1
            if counter[0]==2:
                result["strategy_count"]+=1
            return result
        with patch.object(pub,"run",side_effect=drift):
            with self.assertRaisesRegex(ValueError,"BACKTEST_NOT_REPRODUCIBLE"):
                pub.publish(self.source,self.output)
        self.assertEqual(self.output.read_text(encoding="utf-8"),"previous")


if __name__=="__main__":
    unittest.main()
