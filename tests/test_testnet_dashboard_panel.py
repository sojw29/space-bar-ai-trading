"""Static fail-closed dashboard safety panel regression."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "web" / "command_center.html"
MOBILE_HTML = ROOT / "web" / "audit_room_mobile_v153.html"


class TestDashboardSafetyPanel(unittest.TestCase):
    def test_mobile_panel_is_read_only_and_defaults_to_blocked(self):
        source = MOBILE_HTML.read_text(encoding="utf-8")
        self.assertIn('id="testnet-staging-state"', source)
        self.assertIn('aria-live="polite"', source)
        self.assertIn('"/api/v1/testnet/staging/status"', source)
        self.assertIn('data.status!=="NOT_CONNECTED"', source)
        self.assertIn('data.orders_enabled!==false', source)
        self.assertIn('data.network_enabled!==false', source)
        self.assertIn("상태 확인 불가 · 주문 불가", source)

    def test_panel_is_read_only_and_defaults_to_blocked(self):
        source = HTML.read_text(encoding="utf-8")
        self.assertIn('id="testnet-staging-state"', source)
        self.assertIn('aria-live="polite"', source)
        self.assertIn('"/api/v1/testnet/staging/status"', source)
        self.assertIn('data.status!=="NOT_CONNECTED"', source)
        self.assertIn('data.orders_enabled!==false', source)
        self.assertIn('data.network_enabled!==false', source)
        self.assertIn("상태 확인 불가 · 주문 불가", source)
        self.assertIn("NOT CONNECTED · 오프라인 기록 미연결 · 주문 불가", source)


if __name__ == "__main__":
    unittest.main()
