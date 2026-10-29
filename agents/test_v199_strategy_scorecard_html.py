"""V199 offline HTML export safety and escaping."""
import unittest
from strategy_scorecard_html_v199 import render


def sample():
    return {
        "version": "V105.0", "research_only": True,
        "orders_enabled": False, "live_trading_approved": False,
        "strategy_scorecard": {
            "version": "V197.0", "status": "RESEARCH_COMPARISON_ONLY",
            "ranking_enabled": False, "strategy_selection_enabled": False,
            "orders_allowed": False, "live_trading_approved": False,
            "research_only": True,
            "rows": [{"strategy": "<script>alert(1)</script>",
                      "holdout_trades": 2, "holdout_win_rate_pct": 50,
                      "holdout_net_return_pct": -1.2,
                      "holdout_profit_factor": 0.5,
                      "holdout_max_drawdown_pct": 3.2,
                      "evidence_status": "INSUFFICIENT_EVIDENCE",
                      "evidence_failures": ["insufficient_holdout_trades"]}],
        },
    }


class OfflineHTMLTests(unittest.TestCase):
    def test_escapes_untrusted_names_and_has_no_scripts(self):
        page = render(sample())
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)
        self.assertIn("NO LIVE ORDERS", page)
        self.assertIn("INSUFFICIENT_EVIDENCE", page)

    def test_rejects_live_flag(self):
        report = sample()
        report["orders_enabled"] = True
        with self.assertRaises(ValueError):
            render(report)

    def test_rejects_ranking_flag(self):
        report = sample()
        report["strategy_scorecard"]["ranking_enabled"] = True
        with self.assertRaises(ValueError):
            render(report)

    def test_rejects_nonfinite_metric(self):
        report = sample()
        report["strategy_scorecard"]["rows"][0]["holdout_net_return_pct"] = float("nan")
        with self.assertRaises(ValueError):
            render(report)


if __name__ == "__main__":
    unittest.main()
