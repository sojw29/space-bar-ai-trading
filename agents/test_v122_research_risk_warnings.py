import unittest
from research_risk_warnings_v122 import audit

def summary(**overrides):
    s={"version":"V121.0","evaluated_folds":10,"total_folds":10,
       "hypothetical_sell_events":100,"positive_fold_rate_pct":80,
       "abstention_rate_pct":0,"worst_fold_max_drawdown_pct":3}
    s.update(overrides)
    return s

class ResearchRiskWarningsTests(unittest.TestCase):
    def test_clean_not_approved(self):
        result=audit(summary())
        self.assertEqual(result["warning_count"],0)
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["validated_edge"])

    def test_low_fold_count(self):
        result=audit(summary(evaluated_folds=2,total_folds=2))
        self.assertIn("INSUFFICIENT_FOLDS",[x["code"] for x in result["warnings"]])

    def test_low_trade_count(self):
        result=audit(summary(hypothetical_sell_events=2))
        self.assertIn("INSUFFICIENT_CLOSED_TRADES",[x["code"] for x in result["warnings"]])

    def test_drawdown_warning(self):
        result=audit(summary(worst_fold_max_drawdown_pct=15))
        self.assertIn("EXCESSIVE_SAMPLED_DRAWDOWN",[x["code"] for x in result["warnings"]])

    def test_positive_rate_warning(self):
        result=audit(summary(positive_fold_rate_pct=20))
        self.assertIn("LOW_POSITIVE_FOLD_RATE",[x["code"] for x in result["warnings"]])

    def test_abstention_warning(self):
        result=audit(summary(abstention_rate_pct=60))
        self.assertIn("HIGH_ABSTENTION_RATE",[x["code"] for x in result["warnings"]])

    def test_all_abstain(self):
        result=audit(summary(evaluated_folds=0,total_folds=10,
                             positive_fold_rate_pct=None,
                             worst_fold_max_drawdown_pct=None,
                             abstention_rate_pct=100))
        self.assertIn("NO_EVALUATED_FOLDS",[x["code"] for x in result["warnings"]])

    def test_invalid_threshold(self):
        with self.assertRaisesRegex(ValueError,"INVALID_THRESHOLDS"):
            audit(summary(),min_closed_trades=0)

    def test_bad_metric(self):
        with self.assertRaisesRegex(ValueError,"INVALID_POSITIVE_FOLD_RATE"):
            audit(summary(positive_fold_rate_pct=float("nan")))

    def test_determinism(self):
        self.assertEqual(audit(summary()),audit(summary()))

if __name__=="__main__":
    unittest.main()
