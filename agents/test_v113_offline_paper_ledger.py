import unittest
from decimal import Decimal
from offline_paper_ledger_v113 import PaperLedger, run

class PaperLedgerTests(unittest.TestCase):
    def test_buy_and_sell_hypothetical(self):
        ledger = PaperLedger()
        ledger.buy("100", "500", "2026-10-24")
        self.assertGreater(ledger.units, 0)
        held = ledger.units
        ledger.sell("110", held, "2026-10-24")
        self.assertEqual(ledger.units, 0)
        self.assertGreater(ledger.cash, Decimal("10000"))
        self.assertEqual(ledger.snapshot()["orders_submitted_to_exchange"], 0)

    def test_aggregate_position_limit(self):
        ledger = PaperLedger()
        ledger.buy("100", "900", "2026-10-24")
        with self.assertRaisesRegex(ValueError, "AGGREGATE_POSITION_LIMIT"):
            ledger.buy("100", "200", "2026-10-24")

    def test_cannot_oversell(self):
        ledger = PaperLedger()
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_UNITS"):
            ledger.sell("100", "1", "2026-10-24")

    def test_kill_switch_blocks_new_orders(self):
        ledger = PaperLedger()
        ledger.buy("100", "1000", "2026-10-24")
        ledger.mark("1", "2026-10-24")
        self.assertTrue(ledger.kill_switch)
        with self.assertRaisesRegex(ValueError, "KILL_SWITCH_ACTIVE"):
            ledger.buy("1", "10", "2026-10-24")

    def test_kill_switch_allows_reduction_only_exit(self):
        ledger = PaperLedger()
        ledger.buy("100", "1000", "2026-10-24")
        ledger.mark("1", "2026-10-24")
        self.assertTrue(ledger.kill_switch)
        held = ledger.units
        ledger.sell("1", held, "2026-10-24")
        self.assertEqual(ledger.units, Decimal("0"))
        self.assertTrue(ledger.kill_switch)
        self.assertEqual(ledger.snapshot()["orders_submitted_to_exchange"], 0)
        with self.assertRaisesRegex(ValueError, "KILL_SWITCH_ACTIVE"):
            ledger.buy("1", "1", "2026-10-24")

    def test_invalid_values(self):
        ledger = PaperLedger()
        for value in ("nan", "-1", "0", "Infinity"):
            with self.assertRaises(ValueError):
                ledger.mark(value, "2026-10-24")

    def test_day_cannot_go_backwards(self):
        ledger = PaperLedger()
        ledger.mark("100", "2026-10-25")
        with self.assertRaisesRegex(ValueError, "NON_MONOTONIC_DAY"):
            ledger.mark("100", "2026-10-24")

    def test_command_replay_deterministic(self):
        commands = [{"action":"BUY","price":"100","budget":"500","day":"2026-10-24"},
                    {"action":"SELL","price":"110","units":"4","day":"2026-10-24"}]
        self.assertEqual(run(commands), run(commands))
        self.assertFalse(run(commands)["snapshot"]["exchange_connected"])

    def test_unknown_command_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_COMMAND"):
            run([{"action":"LIVE_BUY","price":"100","day":"2026-10-24"}])

if __name__ == "__main__":
    unittest.main()
