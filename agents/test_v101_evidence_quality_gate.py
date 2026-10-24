import unittest
from evidence_quality_gate_v101 import evaluate

def fixture(n=0):
    return {
        "schema_version":"61.0",
        "mode":"DESCRIPTIVE_HISTORICAL_PAPER_PERFORMANCE",
        "source":"historical_csv_snapshot",
        "realtime":False, "paper_only":True,
        "orders_enabled":False, "live_trading_approved":False,
        "oos_validated":False, "independent_oos_verified":False,
        "paper_closed_trades":n,
        "performance_sample_minimum_closed_trades":30,
        "performance_sample_sufficient":n>=30,
        "paper_max_observed_drawdown_pct":1.5,
        "paper_realized_net":-5.0
    }

class EvidenceQualityTests(unittest.TestCase):
    def test_small_sample_blocked(self):
        result=evaluate(fixture(5))
        self.assertEqual(result["status"],"EVIDENCE_INSUFFICIENT")
        self.assertEqual(result["checks"][0]["status"],"BLOCKED")
        self.assertFalse(result["live_trading_approved"])

    def test_large_sample_still_not_validated(self):
        result=evaluate(fixture(100))
        self.assertEqual(result["checks"][0]["status"],"PASS")
        self.assertEqual(result["status"],"EVIDENCE_INSUFFICIENT")
        self.assertFalse(result["strategy_profitable_verified"])

    def test_unsafe_order_flag_rejected(self):
        report=fixture()
        report["orders_enabled"]=True
        with self.assertRaises(ValueError):
            evaluate(report)

    def test_false_out_of_sample_claim_rejected(self):
        report=fixture()
        report["independent_oos_verified"]=True
        with self.assertRaises(ValueError):
            evaluate(report)

    def test_inconsistent_sample_rejected(self):
        report=fixture(31)
        report["performance_sample_sufficient"]=False
        with self.assertRaises(ValueError):
            evaluate(report)

    def test_nonfinite_performance_rejected(self):
        report=fixture()
        report["paper_realized_net"]=float("nan")
        with self.assertRaises(ValueError):
            evaluate(report)

if __name__=="__main__":
    unittest.main()
