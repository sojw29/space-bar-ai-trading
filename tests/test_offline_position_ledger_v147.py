import unittest
from agents.offline_paper_execution_v145 import simulate_fill
from agents.offline_position_ledger_v147 import PositionLedger


def fill(side, qty, price, fee_bps=10):
    return simulate_fill(side=side, quantity=qty, reference_price=price,
                         available_volume=100000, max_participation=1,
                         spread_bps=0, slippage_bps=0, fee_bps=fee_bps)


class PositionLedgerTests(unittest.TestCase):
    def test_long_partial_close_and_fees(self):
        p = PositionLedger()
        p.apply(fill("BUY", 2, 100))
        self.assertEqual(p.signed_qty, 2)
        profit = p.apply(fill("SELL", 1, 110))
        self.assertAlmostEqual(profit, 10 - .1 - .11)
        self.assertEqual(p.signed_qty, 1)
        self.assertAlmostEqual(p.unrealized_pnl(110), 10 - .1)

    def test_short_close(self):
        p = PositionLedger()
        p.apply(fill("SELL", 1, 100))
        self.assertAlmostEqual(p.apply(fill("BUY", 1, 90)), 10 - .1 - .09)
        self.assertEqual(p.signed_qty, 0)
        self.assertEqual(p.average_entry, 0)

    def test_reversal(self):
        p = PositionLedger()
        p.apply(fill("BUY", 1, 100))
        pnl = p.apply(fill("SELL", 2, 110))
        self.assertAlmostEqual(pnl, 10 - .1 - .11)
        self.assertEqual(p.signed_qty, -1)
        self.assertEqual(p.average_entry, 110)
        self.assertAlmostEqual(p.deferred_entry_fees, .11)

    def test_weighted_average(self):
        p = PositionLedger()
        p.apply(fill("BUY", 1, 100))
        p.apply(fill("BUY", 3, 120))
        self.assertEqual(p.average_entry, 115)
        self.assertEqual(p.signed_qty, 4)


if __name__ == "__main__":
    unittest.main()
