import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from news_research_reproducibility_v141 import build,write_bundle,verify_bundle,ARTIFACTS

class NewsReproducibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.raw=root/"raw.json"
        self.csv=root/"candles.csv"
        self.output=root/"bundle"
        self.raw.write_text(json.dumps({"articles":[{
            "url":"https://example.org/btc","title":"Bitcoin ETF news",
            "domain":"example.org","seendate":"20261024090500"}]}),encoding="utf-8")
        start=datetime(2026,10,24,9,tzinfo=timezone.utc)
        rows=["timestamp,open,high,low,close,volume"]
        for i in range(90):
            stamp=(start+timedelta(minutes=i)).isoformat()
            rows.append(f"{stamp},100,102,99,101,10")
        self.csv.write_text("\n".join(rows)+"\n",encoding="utf-8")
    def create(self):
        return write_bundle(self.output,self.raw,self.csv,"BTC",
                            "2026-10-24T10:00:00+00:00",1,60)
    def test_build_all_artifacts(self):
        self.assertEqual(set(build(self.raw,self.csv,"BTC","2026-10-24T10:00:00Z",1)),set(ARTIFACTS))
    def test_create_bundle(self):
        self.assertEqual(self.create()["version"],"V141.0")
    def test_replay(self):
        self.create()
        self.assertTrue(verify_bundle(self.output,self.raw,self.csv)["reproducible"])
    def test_artifact_count(self):
        self.create()
        self.assertEqual(verify_bundle(self.output,self.raw,self.csv)["artifact_count"],7)
    def test_modified_raw_refused(self):
        self.create()
        data=json.loads(self.raw.read_text(encoding="utf-8"))
        data["articles"][0]["title"]="Changed Bitcoin ETF news"
        self.raw.write_text(json.dumps(data),encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_bundle(self.output,self.raw,self.csv)
    def test_modified_output_refused(self):
        self.create()
        (self.output/"taxonomy.json").write_text("{}",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"OUTPUT_REPLAY_MISMATCH"):
            verify_bundle(self.output,self.raw,self.csv)
    def test_modified_manifest_refused(self):
        self.create()
        path=self.output/"bundle.json"
        data=json.loads(path.read_text(encoding="utf-8"))
        data["input_manifest"]["manifest_sha256"]="0"*64
        path.write_text(json.dumps(data),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"INPUT_MANIFEST_MISMATCH"):
            verify_bundle(self.output,self.raw,self.csv)
    def test_refuse_overwrite(self):
        self.create()
        with self.assertRaisesRegex(ValueError,"OUTPUT_ALREADY_EXISTS"):
            self.create()
    def test_bad_min_samples(self):
        with self.assertRaisesRegex(ValueError,"INVALID_MIN_SAMPLES"):
            build(self.raw,self.csv,"BTC","2026-10-24T10:00:00Z",0)
    def test_bad_window(self):
        with self.assertRaisesRegex(ValueError,"INVALID_CLUSTER_WINDOW"):
            build(self.raw,self.csv,"BTC","2026-10-24T10:00:00Z",1,0)
    def test_no_trading(self):
        self.create()
        r=verify_bundle(self.output,self.raw,self.csv)
        self.assertEqual(r["orders_submitted_to_exchange"],0)
        self.assertFalse(r["validated_edge"])
    def test_output_hash_count(self):
        self.assertEqual(len(self.create()["output_sha256"]),7)

if __name__=="__main__":
    unittest.main()
