"""V219 static browser-room entrypoint safety checks."""
import unittest
from pathlib import Path

WEB=Path(__file__).resolve().parent.parent/"web"


class BrowserRoomTests(unittest.TestCase):
    def test_entrypoint_links_existing_rooms(self):
        page=(WEB/"index.html").read_text(encoding="utf-8")
        self.assertIn('href="./office_3d.html"',page)
        self.assertIn('href="./command_center.html"',page)
        self.assertTrue((WEB/"office_3d.html").is_file())
        self.assertTrue((WEB/"command_center.html").is_file())

    def test_static_site_discloses_backend_limitations(self):
        page=(WEB/"index.html").read_text(encoding="utf-8")
        self.assertIn("읽기 전용 데모",page)
        self.assertIn("API",page)
        self.assertIn("주문 실행 비활성",page)

    def test_pages_workflow_only_deploys_static_web(self):
        flow=(WEB.parent/".github/workflows/deploy_browser_room.yml").read_text(encoding="utf-8")
        self.assertIn("path: web",flow)
        self.assertIn("actions/deploy-pages@",flow)
        self.assertNotIn("secrets.",flow)


if __name__=="__main__":
    unittest.main()
