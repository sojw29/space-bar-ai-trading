import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from paper_performance_v114 import analyze, run

class PaperPerformanceTests(unittest.TestCase):
    def test_empty_commands(self):
        result = analyze([])
        self.assertEqual(Decimal(result["total_return_pct"]), 0)
        self.assertEqual(Decimal(result["max_drawdown_pct"]), 0)
        self.assertEqual(result["timeline"], [])

    def test_profitable_round_trip_after_fees(self):
        commands = [
            {"action":"BUY","price":"100","budget":"500","day":"2026-10-24"},
            {"action":"MARK","price":"110","day":"2026-10-24"},
            {"action":"SELL","price":"110","units":"4","day":"2026-10-24"},
        ]
        result = analyze(commands)
        self.assertGreater(Decimal(result["total_return_pct"]), 0)
        self.assertEqual(result["hypothetical_buy_events"], 1)
        self.assertEqual(result["hypothetical_sell_events"], 1)
        self.assertGreater(Decimal(result["fees_paid"]), 0)
        self.assertEqual(result["orders_submitted_to_exchange"], 0)

    def test_drawdown_sampled(self):
        commands = [
            {"action":"BUY","price":"100","budget":"1000","day":"2026-10-24"},
            {"action":"MARK","price":"50","day":"2026-10-24"},
        ]
        result = analyze(commands)
        self.assertGreater(Decimal(result["max_drawdown_pct"]), 0)
        self.assertLess(Decimal(result["total_return_pct"]), 0)

    def test_kill_switch_visible(self):
        commands = [
            {"action":"BUY","price":"100","budget":"1000","day":"2026-10-24"},
            {"action":"MARK","price":"1","day":"2026-10-24"},
        ]
        self.assertTrue(analyze(commands)["kill_switch_active"])

    def test_replay_deterministic(self):
        commands = [{"action":"MARK","price":"100","day":"2026-10-24"}]
        self.assertEqual(analyze(commands), analyze(commands))

    def test_reject_unknown_command(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_COMMAND"):
            analyze([{"action":"LIVE_BUY","price":"100","day":"2026-10-24"}])

    def test_reject_oversell(self):
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_UNITS"):
            analyze([{"action":"SELL","price":"100","units":"1","day":"2026-10-24"}])

    def test_json_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"commands.json"
            path.write_text(json.dumps([{"action":"MARK","price":"100","day":"2026-10-24"}]))
            self.assertEqual(len(run(path)["timeline"]), 1)

if __name__ == "__main__":
    unittest.main()
