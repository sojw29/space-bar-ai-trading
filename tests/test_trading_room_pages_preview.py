"""Safety regression for the manually deployed static trading room preview."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/trading-room-pages-preview.yml"
PREVIEW = ROOT / "web/space_bar_preview.html"


class TestTradingRoomPagesPreview(unittest.TestCase):
    def test_pages_deployment_is_manual_and_main_only(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("cp web/space_bar_preview.html _site/index.html", workflow)
        self.assertIn("assert \"<script\" not in page.lower()", workflow)
        self.assertIn('assert "fetch(" not in page.lower()', workflow)

    def test_command_center_has_all_six_read_only_stations(self):
        html = PREVIEW.read_text(encoding="utf-8")
        self.assertIn('aria-label="AI 트레이딩룸 정적 배치도"', html)
        self.assertIn("시각적 배치도 · 에이전트 미실행 · 거래 승인 없음", html)
        for agent in ("ATLAS", "QUANT", "GUARDIAN", "ORACLE", "TESTER", "COMMANDER"):
            self.assertIn(f"<strong>{agent}</strong>", html)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))", html)
        self.assertIn("@media(max-width:480px)", html)
        self.assertNotIn("<script", html.lower())

    def test_public_preview_is_static_and_explicitly_not_connected(self):
        html = PREVIEW.read_text(encoding="utf-8")
        self.assertIn("OFFLINE PREVIEW", html)
        self.assertIn("NO ORDERS", html)
        self.assertIn("NOT CONNECTED", html)
        self.assertIn("PREVIEW ONLY", html)
        self.assertIn("DISABLED", html)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("fetch(", html.lower())
        self.assertNotIn("api/v1/", html.lower())


if __name__ == "__main__":
    unittest.main()
