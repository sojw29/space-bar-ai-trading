import unittest

from agents.offline_paper_execution_v145 import simulate_fill


class OfflinePaperExecutionTests(unittest.TestCase):
    def test_buy_sell_spread_slippage(self):
        buy = simulate_fill(side="BUY", quantity=1, reference_price=100,
                            available_volume=1000)
        sell = simulate_fill(side="SELL", quantity=1, reference_price=100,
                             available_volume=1000)
        self.assertGreater(buy.fill_price, 100)
        self.assertLess(sell.fill_price, 100)
        self.assertGreater(buy.fee, 0)
        self.assertGreater(sell.slippage_cost, 0)

    def test_spread_and_slippage_are_accounted_separately(self):
        fill = simulate_fill(side="BUY", quantity=1, reference_price=100,
                             available_volume=1000, spread_bps=2,
                             slippage_bps=3, fee_bps=0)
        self.assertAlmostEqual(fill.spread_cost, 0.01)
        self.assertAlmostEqual(fill.slippage_cost, 0.03)
        self.assertAlmostEqual(fill.fill_price - fill.reference_price,
                               fill.spread_cost + fill.slippage_cost)
        self.assertEqual(fill.fee, 0)

    def test_zero_slippage_with_nonzero_spread(self):
        fill = simulate_fill(side="SELL", quantity=1, reference_price=100,
                             available_volume=1000, spread_bps=2,
                             slippage_bps=0)
        self.assertAlmostEqual(fill.spread_cost, 0.01)
        self.assertEqual(fill.slippage_cost, 0)

    def test_reject_illiquid_order(self):
        self.assertIsNone(simulate_fill(side="BUY", quantity=2,
                                       reference_price=100, available_volume=100))

    def test_invalid_assumptions_rejected_even_if_illiquid(self):
        with self.assertRaises(ValueError):
            simulate_fill(side="BUY", quantity=2, reference_price=100,
                          available_volume=100, spread_bps=300000)

    def test_arithmetic_overflow_rejected(self):
        with self.assertRaises(ValueError):
            simulate_fill(side="BUY", quantity=1e308,
                          reference_price=1e308, available_volume=1e308,
                          max_participation=1.0)

    def test_invalid_inputs_fail_closed(self):
        cases = [
            dict(side="HOLD"), dict(quantity=0), dict(reference_price=0),
            dict(available_volume=-1), dict(spread_bps=-1),
            dict(slippage_bps=float("nan")), dict(fee_bps=float("inf")),
            dict(max_participation=2), dict(quantity=True),
            dict(spread_bps=300000),
        ]
        for override in cases:
            with self.subTest(override=override), self.assertRaises(ValueError):
                simulate_fill(**(dict(side="BUY", quantity=1, reference_price=100,
                                      available_volume=1000) | override))


if __name__ == "__main__":
    unittest.main()
