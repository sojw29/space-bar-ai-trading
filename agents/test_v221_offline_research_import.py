"""V221 static Pages offline scorecard import contracts."""
import unittest
from pathlib import Path

ROOM=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text(encoding="utf-8")

class OfflineResearchImportTests(unittest.TestCase):
    def test_file_import_remains_validated(self):
        self.assertIn('input.addEventListener("change",async function()',ROOM)
        self.assertIn('file.size>2000000',ROOM)
        self.assertIn('renderRows(validate(data),"직접 선택한 파일")',ROOM)
        self.assertIn("data.research_only!==true",ROOM)
        self.assertIn("data.orders_enabled!==false",ROOM)

    def test_static_pages_skips_unavailable_local_api(self):
        self.assertIn('if(!isStaticPages&&(location.protocol==="http:"||location.protocol==="https:"))loadLocalSnapshot()',ROOM)
        self.assertIn('if(!isStaticPages)refresh.addEventListener("click",loadLocalSnapshot)',ROOM)
        self.assertIn('fetch("./research_snapshot.json"',ROOM)
        self.assertIn("JSON 파일을 직접 선택할 수 있습니다",ROOM)

    def test_classic_scorecard_script_has_own_static_pages_binding(self):
        # The V220 declaration lives in a module script, not this classic IIFE.
        scorecard_script=ROOM.split("/* V200: local-only scorecard import.",1)[1]
        self.assertIn('const isStaticPages = location.hostname.endsWith(".github.io");',scorecard_script)

    def test_static_pages_user_message(self):
        self.assertIn("공개 연구 스냅샷 확인 중",ROOM)
        self.assertIn("refresh.title=",ROOM)

    def test_no_remote_code_or_trade_execution(self):
        self.assertNotIn("eval(",ROOM)
        self.assertIn("주문",ROOM)

if __name__=="__main__":
    unittest.main()
