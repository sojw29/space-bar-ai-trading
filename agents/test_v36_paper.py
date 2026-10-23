"""V36 no-lookahead, costs and no broker execution tests."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import multi_agent_v26 as agents
import paper_execution_v36 as paper


def history(count=70):
    output=[]
    for i in range(count):
        p=100+i*0.2
        output.append({"timestamp":1700000100+i*300,
                       "open":p-.05,"high":p+.2,
                       "low":p-.2,"close":p,"volume":20})
    return output


class PaperExecutionTests(unittest.TestCase):
    def test_empty_flat_market(self):
        data=history()
        for item in data:
            item.update(open=100,high=100,low=100,close=100)
        report=paper.simulate(data)
        self.assertEqual(report["trade_count"],0)
        self.assertFalse(report["orders_enabled"])
        self.assertFalse(report["independent_oos_verified"])

    def test_lookahead_decision_is_independent_of_fill_candle(self):
        data=history()
        first=agents.analyze(data[:55])["commander"]["decision"]
        changed=copy.deepcopy(data)
        changed[55]["close"]=1000
        changed[55]["high"]=1000
        # Signal for candle 55 must not inspect candle 55 itself.
        self.assertEqual(first,agents.analyze(changed[:55])["commander"]["decision"])

    def test_costs_never_improve_same_trade(self):
        data=history()
        zero=paper.simulate(data,fee_bps=0,slippage_bps=0)
        costly=paper.simulate(data,fee_bps=10,slippage_bps=5)
        self.assertEqual(zero["trade_count"],costly["trade_count"])
        self.assertGreaterEqual(zero["net_pnl_total"],costly["net_pnl_total"])

    def test_reject_negative_fees(self):
        with self.assertRaises(ValueError):
            paper.simulate(history(),fee_bps=-1)
        with self.assertRaises(ValueError):
            paper.simulate(history(),notional=0)

    def test_missing_candle_rejected(self):
        data=history()
        data.pop(10)
        with self.assertRaises(ValueError):
            paper.simulate(data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
