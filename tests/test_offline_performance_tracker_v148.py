import unittest
from agents.offline_performance_tracker_v148 import PerformanceTracker


class PerformanceTrackerTests(unittest.TestCase):
    def test_drawdown_and_streak(self):
        p = PerformanceTracker(1000)
        for pnl in (100, -50, -50, 20):
            p.record_closed_trade(pnl)
        self.assertAlmostEqual(p.max_drawdown_pct, 100 * 100 / 1100)
        self.assertEqual(p.longest_losing_streak, 2)
        self.assertEqual(p.consecutive_losses, 0)
        self.assertEqual(p.equity, 1020)
        self.assertAlmostEqual(p.win_rate_pct, 50)

    def test_no_trades(self):
        p = PerformanceTracker(100)
        self.assertEqual(p.win_rate_pct, 0)
        self.assertIsNone(p.profit_factor)

    def test_reject_invalid(self):
        p = PerformanceTracker(100)
        for value in (float("nan"), float("inf"), True, -101):
            with self.assertRaises(ValueError):
                p.record_closed_trade(value)
        self.assertEqual(p.equity, 100)

    def test_break_even(self):
        p = PerformanceTracker(100)
        p.record_closed_trade(0)
        self.assertEqual(p.breakeven, 1)
        self.assertEqual(p.win_rate_pct, 0)


if __name__ == "__main__":
    unittest.main()
