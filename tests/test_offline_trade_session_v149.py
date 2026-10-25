import unittest
from agents.offline_paper_execution_v145 import simulate_fill
from agents.offline_trade_session_v149 import OfflineTradeSession


def fill(side, quantity, price):
    return simulate_fill(side=side, quantity=quantity, reference_price=price,
                         available_volume=1000, max_participation=1,
                         spread_bps=0, slippage_bps=0, fee_bps=10)


class SessionTests(unittest.TestCase):
    def test_partial_close_record_once(self):
        s = OfflineTradeSession(1000)
        s.apply_fill(fill("BUY", 2, 100))
        s.apply_fill(fill("SELL", 1, 110))
        self.assertEqual(len(s.performance.records), 0)
        s.apply_fill(fill("SELL", 1, 120))
        self.assertEqual(len(s.performance.records), 1)
        self.assertAlmostEqual(s.performance.records[0], 30 - .2 - .11 - .12)
        self.assertAlmostEqual(s.performance.equity, 1029.57)

    def test_short_roundtrip(self):
        s = OfflineTradeSession(1000)
        s.apply_fill(fill("SELL", 1, 100))
        s.apply_fill(fill("BUY", 1, 90))
        self.assertAlmostEqual(s.performance.records[0], 9.81)

    def test_reversal_rejected_without_mutation(self):
        s = OfflineTradeSession(1000)
        s.apply_fill(fill("BUY", 1, 100))
        with self.assertRaises(ValueError):
            s.apply_fill(fill("SELL", 2, 110))
        self.assertEqual(s.ledger.signed_qty, 1)
        self.assertEqual(len(s.performance.records), 0)


if __name__ == "__main__":
    unittest.main()
