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

    def test_command_center_has_all_ten_read_only_stations(self):
        html = PREVIEW.read_text(encoding="utf-8")
        self.assertIn('aria-label="AI 트레이딩룸 정적 배치도"', html)
        self.assertIn("시각적 배치도 · 에이전트 미실행 · 거래 승인 없음", html)
        for agent in ("COMMANDER", "ATLAS", "ORACLE", "QUANT", "SCALPER", "TESTER", "GUARDIAN", "EXECUTOR", "EVOLVE", "AUDITOR"):
            self.assertIn(f"<strong>{agent}</strong>", html)
        self.assertEqual(html.count('class="station"') + html.count('class="station command"'), 10)
        for agent in ("COMMANDER", "ATLAS", "ORACLE", "QUANT", "SCALPER", "TESTER", "GUARDIAN", "EXECUTOR", "EVOLVE", "AUDITOR"):
            self.assertEqual(html.count(f"<strong>{agent}</strong>"), 1)
        self.assertIn("<strong>EXECUTOR</strong><span>DISABLED</span>", html)
        self.assertIn("<strong>COMMANDER</strong><span>NO ORDERS</span>", html)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))", html)
        self.assertIn("@media(max-width:480px)", html)
        self.assertNotIn("<script", html.lower())

    def test_local_audit_room_resets_stale_meeting_state_and_blocks_orders(self):
        dashboard = (ROOT / "web/audit_room_mobile_v153.html").read_text(encoding="utf-8")
        self.assertIn('setRosterMeetingState(null,"");\n document.getElementById("meeting-steps").replaceChildren();', dashboard)
        self.assertIn('setRosterMeetingState(data.transcript,sourceLabel);', dashboard)
        self.assertIn('data.trade_authorization!=="DENIED"', dashboard)
        self.assertIn('data.orders_enabled!==false', dashboard)
        self.assertIn('state.textContent="회의 기록 미연결 · 거래 승인 없음"', dashboard)
        self.assertIn('li.dataset.phase=entry.phase', dashboard)
        self.assertIn('summary.textContent=entry.summary', dashboard)
        self.assertNotIn('summary.innerHTML=entry.summary', dashboard)

    def test_command_center_ten_role_map_does_not_claim_execution(self):
        html = (ROOT / "web/command_center.html").read_text(encoding="utf-8")
        roster = html.split('id="team-role-map"', 1)[1].split("</div>\n<p class=\"muted\">기존 시장", 1)[0]
        for name in ("COMMANDER", "ATLAS", "ORACLE", "QUANT", "SCALPER", "TESTER", "GUARDIAN", "EXECUTOR", "EVOLVE", "AUDITOR"):
            self.assertEqual(roster.count(f"<strong>{name}</strong>"), 1)
        self.assertIn("DISABLED · 주문 실행 권한 없음", roster)
        self.assertIn("이 화면에 별도 데이터 연결 없음", roster)
        self.assertIn("시장 이벤트 책상 없음", roster)

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
