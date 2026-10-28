"""V188: fail-closed meeting API verdict HUD contract."""
import unittest
from pathlib import Path

HTML = Path("web/office_3d.html").read_text(encoding="utf-8")


class V188ApiVerdictTests(unittest.TestCase):
    def test_read_only_verdict_panel(self):
        self.assertIn('id="v188-api-verdict"', HTML)
        self.assertIn('data-verdict="BLOCKED"', HTML)
        self.assertIn('function showApiVerdict(validation)', HTML)

    def test_requires_strict_server_verdict(self):
        for term in (
            'validation.verified===true',
            'validation.status==="VERIFIED_RESEARCH"',
            'validation.orders_allowed===false',
            'validation.live_trading_allowed===false',
            'Array.isArray(validation.failures)',
            'validation.failures.length===0',
        ):
            self.assertIn(term, HTML)

    def test_missing_or_bad_verdict_blocks_meeting(self):
        self.assertIn('const apiContractValid=showApiVerdict(data.contract_validation);', HTML)
        self.assertIn('if(!apiContractValid){blocked("API 검증 계약 불일치");return;}', HTML)
        self.assertIn('showApiVerdict(null);', HTML)
        self.assertIn('  inspectAgent();\n  showApiVerdict(null);', HTML)

    def test_never_enables_orders(self):
        self.assertNotIn('orders_enabled=true', HTML)
        self.assertNotIn('live_trading_approved=true', HTML)


if __name__ == "__main__":
    unittest.main()
