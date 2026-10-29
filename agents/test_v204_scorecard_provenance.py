"""V204 provenance publishing and 3D room rendering contracts."""
import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from publish_scorecard_v203 import publish


class ProvenanceTests(unittest.TestCase):
    def test_snapshot_contains_descriptive_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/"history.csv"
            with source.open("w",newline="",encoding="utf-8") as stream:
                writer=csv.DictWriter(stream,fieldnames=["timestamp","open","high","low","close","volume"])
                writer.writeheader()
                for i in range(600):
                    price=100+i*0.02+(5 if (i//25)%2 else -5)
                    writer.writerow({"timestamp":1700000000000+i*300000,
                        "open":price,"high":price+1,"low":price-1,"close":price,
                        "volume":150 if i%17==0 else 80})
            target=Path(tmp)/"snapshot.json"
            publish(source,target)
            result=json.loads(target.read_text(encoding="utf-8"))
            p=result["snapshot_provenance"]
            self.assertEqual(p["version"],"V204.0")
            self.assertEqual(p["history_sha256"],hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(p["history_last_timestamp_raw"],str(1700000000000+599*300000))
            self.assertFalse(p["data_authenticity_verified"])
            self.assertFalse(p["history_timestamp_verified"])
            self.assertFalse(p["realtime"])
            self.assertIsNotNone(datetime.fromisoformat(p["generated_at_utc"].replace("Z","+00:00")))

    def test_room_displays_unverified_provenance(self):
        html=(Path(__file__).resolve().parents[1]/"web"/"office_3d.html").read_text(encoding="utf-8")
        self.assertIn('id="v204-scorecard-provenance"',html)
        self.assertIn("renderProvenance(data)",html)
        self.assertIn('p.data_authenticity_verified!==false',html)
        self.assertIn('label.textContent=',html)
        self.assertIn("과거 데이터/진위 미검증",html)


if __name__=="__main__":
    unittest.main()
