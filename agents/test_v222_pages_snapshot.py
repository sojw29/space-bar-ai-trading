import json
import tempfile
import unittest
from pathlib import Path
from pages_snapshot_v222 import stage

class PagesSnapshotTests(unittest.TestCase):
    def test_missing_source_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertFalse(stage(root/"missing.json",root/"public.json"))
            self.assertFalse((root/"public.json").exists())

    def test_invalid_and_unsafe_snapshots_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/"input.json";dst=root/"public.json"
            for payload in ([],{},{"version":"V105.0","orders_enabled":True}):
                src.write_text(json.dumps(payload),encoding="utf-8")
                dst.write_text('{"stale":true}',encoding="utf-8")
                with self.assertRaises(ValueError):
                    stage(src,dst)
                self.assertFalse(dst.exists())

    def test_invalid_json_or_oversized_source_clears_stale_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/"input.json";dst=root/"public.json"
            for payload in ("{invalid", "x"*2_000_001):
                src.write_text(payload,encoding="utf-8")
                dst.write_text('{"stale":true}',encoding="utf-8")
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    stage(src,dst)
                self.assertFalse(dst.exists())

    def test_source_cannot_be_its_own_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"same.json"
            src.write_text('{"original":true}',encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"SNAPSHOT_SOURCE_DESTINATION_SAME"):
                stage(src,src)
            self.assertEqual(src.read_text(encoding="utf-8"),'{"original":true}')

    def test_static_room_checks_provenance_and_safety(self):
        room=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text(encoding="utf-8")
        self.assertIn('fetch("./research_snapshot.json"',room)
        self.assertIn('renderRows(validate(data),"공개 과거 연구 스냅샷 · 실시간 아님")',room)
        self.assertIn('renderProvenance(data)',room)

if __name__=="__main__": unittest.main()
