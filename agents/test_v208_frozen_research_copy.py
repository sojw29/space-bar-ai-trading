"""V208 frozen copy safety and cleanup regression."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import publish_scorecard_v203 as pub


class FrozenCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source=Path(self.temp.name)/"BTC_5m.csv"
        self.output=Path(self.temp.name)/"snapshot.json"
        with self.source.open("w",newline="",encoding="utf-8") as handle:
            writer=csv.DictWriter(handle,fieldnames=["timestamp","open","high","low","close","volume"])
            writer.writeheader()
            for i in range(600):
                p=100+i*.02+(5 if (i//25)%2 else -5)
                writer.writerow({"timestamp":1700000100+i*300,"open":p,
                    "high":p+1,"low":p-1,"close":p,
                    "volume":150 if i%17==0 else 80})

    def test_pipeline_uses_copy_not_original(self):
        actual=pub.run
        paths=[]
        def spy(path,*args,**kwargs):
            paths.append(Path(path))
            self.assertNotEqual(Path(path).resolve(),self.source.resolve())
            self.assertEqual(pub._sha256_file(path),pub._sha256_file(self.source))
            return actual(path,*args,**kwargs)
        with patch.object(pub,"run",side_effect=spy):
            pub.publish(self.source,self.output)
        # V209 intentionally runs the same frozen history twice for reproducibility.\n        self.assertEqual(len(paths),2)\n        self.assertEqual(paths[0],paths[1])
        self.assertFalse(paths[0].exists())
        data=json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(data["snapshot_provenance"]["source_type"],
                         "LOCAL_HISTORICAL_CSV_FROZEN_COPY")

    def test_snapshot_copy_mismatch_preserves_previous_output(self):
        self.output.write_text("previous",encoding="utf-8")
        original=pub._sha256_file
        count=[0]
        def bad_hash(path):
            count[0]+=1
            if count[0]==2:
                return "0"*64
            return original(path)
        with patch.object(pub,"_sha256_file",side_effect=bad_hash):
            with self.assertRaisesRegex(ValueError,"HISTORY_CHANGED_DURING_SNAPSHOT"):
                pub.publish(self.source,self.output)
        self.assertEqual(self.output.read_text(encoding="utf-8"),"previous")


if __name__=="__main__":
    unittest.main()
