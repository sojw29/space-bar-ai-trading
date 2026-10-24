import tempfile
import unittest
from pathlib import Path
from news_data_provenance_v139 import ROLES,digest,manifest,compare

SETTINGS={"topic":"BTC","observed_at":"2026-10-24T10:00:00Z",
          "min_samples":5,"cluster_window_minutes":60}
class NewsProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.files={}
        for role in ROLES:
            path=Path(self.temp.name)/(role+".json")
            path.write_bytes(role.encode())
            self.files[role]=path
    def test_manifest(self):
        self.assertEqual(manifest(self.files,SETTINGS)["version"],"V139.0")
    def test_digest(self):
        self.assertEqual(len(digest(self.files["raw_news"])["sha256"]),64)
    def test_same_inputs(self):
        m=manifest(self.files,SETTINGS)
        self.assertTrue(compare(m,m)["exact_input_and_settings_match"])
    def test_changed_bytes(self):
        first=manifest(self.files,SETTINGS)
        self.files["raw_news"].write_bytes(b"different")
        second=manifest(self.files,SETTINGS)
        self.assertFalse(compare(first,second)["exact_input_and_settings_match"])
        self.assertFalse(compare(first,second)["input_matches"]["raw_news"])
    def test_changed_settings(self):
        first=manifest(self.files,SETTINGS)
        second=manifest(self.files,{**SETTINGS,"min_samples":6})
        self.assertFalse(compare(first,second)["setting_matches"]["min_samples"])
    def test_missing_file(self):
        self.files["raw_news"].unlink()
        with self.assertRaisesRegex(ValueError,"MISSING_INPUT_FILE"):
            manifest(self.files,SETTINGS)
    def test_missing_role(self):
        with self.assertRaisesRegex(ValueError,"INVALID_INPUT_ROLES"):
            manifest({"raw_news":self.files["raw_news"]},SETTINGS)
    def test_invalid_topic(self):
        with self.assertRaisesRegex(ValueError,"INVALID_TOPIC"):
            manifest(self.files,{**SETTINGS,"topic":"DOGE"})
    def test_invalid_window(self):
        with self.assertRaisesRegex(ValueError,"INVALID_SETTINGS"):
            manifest(self.files,{**SETTINGS,"cluster_window_minutes":0})
    def test_invalid_manifest(self):
        with self.assertRaisesRegex(ValueError,"INVALID_MANIFEST"):
            compare({"version":"V138.0"},manifest(self.files,SETTINGS))
    def test_tamper(self):
        a=manifest(self.files,SETTINGS)
        b=manifest(self.files,SETTINGS)
        b["settings"]["min_samples"]=99
        with self.assertRaisesRegex(ValueError,"MANIFEST_DIGEST_MISMATCH"):
            compare(a,b)
    def test_no_orders(self):
        m=manifest(self.files,SETTINGS)
        self.assertEqual(m["orders_submitted_to_exchange"],0)
        self.assertFalse(m["first_tradable_availability_verified"])
    def test_determinism(self):
        self.assertEqual(manifest(self.files,SETTINGS),manifest(self.files,SETTINGS))

if __name__=="__main__":
    unittest.main()
