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
                with self.assertRaises(ValueError):
                    stage(src,dst)
                self.assertFalse(dst.exists())

    def test_static_room_checks_provenance_and_safety(self):
        room=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text(encoding="utf-8")
        self.assertIn('fetch("./research_snapshot.json"',room)
        self.assertIn('renderRows(validate(data),"공개 과거 연구 스냅샷 · 실시간 아님")',room)
        self.assertIn('renderProvenance(data)',room)

if __name__=="__main__": unittest.main()
