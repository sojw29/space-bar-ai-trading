"""V220 static-hosting safety regressions."""
import unittest
from pathlib import Path

ROOM=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text(encoding="utf-8")

class StaticPagesSafetyTests(unittest.TestCase):
    def test_static_pages_identification(self):
        self.assertIn('location.hostname.endsWith(".github.io")',ROOM)
        self.assertIn('if(isStaticPages)staticPagesNotice();',ROOM)

    def test_explicit_no_backend_notice(self):
        self.assertIn("GitHub Pages에는 AI 분석 서버가 없습니다",ROOM)
        self.assertIn("실시간 분석·매매가 실행 중이지 않습니다",ROOM)

    def test_fail_closed_before_fetching_agents(self):
        start=ROOM.index("async function verifyFeedStatus(){")
        end=ROOM.index("const response=await fetch",start)
        self.assertIn("if(isStaticPages)throw Error",ROOM[start:end])
        self.assertIn("orders_enabled!==false",ROOM)
        self.assertIn('fetch("/api/v1/agents"',ROOM)

if __name__=="__main__":
    unittest.main()
