import unittest
from agents.offline_paper_orders_v146 import PaperOrder


class PaperOrderTests(unittest.TestCase):
    def test_partial_then_full(self):
        o = PaperOrder("BUY", 2, created_bar=10, ttl_bars=3)
        f = o.advance(bar=11, close=100, volume=100, participation=.01)
        self.assertEqual(f.quantity, 1)
        self.assertEqual(o.status, "PARTIAL")
        f = o.advance(bar=12, close=101, volume=200, participation=.01)
        self.assertEqual(f.quantity, 1)
        self.assertEqual(o.status, "FILLED")

    def test_expiry_and_cancel(self):
        o = PaperOrder("SELL", 2, 1, ttl_bars=1)
        self.assertIsNone(o.advance(bar=3, close=100, volume=100))
        self.assertEqual(o.status, "EXPIRED")
        o2 = PaperOrder("BUY", 1, 1)
        o2.cancel()
        self.assertIsNone(o2.advance(bar=2, close=100, volume=100))
        self.assertEqual(o2.status, "CANCELLED")

    def test_no_same_bar_double_fill(self):
        o = PaperOrder("BUY", 10, 1)
        o.advance(bar=2, close=100, volume=100)
        with self.assertRaises(ValueError):
            o.advance(bar=2, close=100, volume=100)

    def test_no_lookahead(self):
        o = PaperOrder("BUY", 1, 10)
        with self.assertRaises(ValueError):
            o.advance(bar=10, close=100, volume=100)

    def test_invalid_volume(self):
        o = PaperOrder("BUY", 1, 1)
        with self.assertRaises(ValueError):
            o.advance(bar=2, close=100, volume=float("nan"))


if __name__ == "__main__":
    unittest.main()
