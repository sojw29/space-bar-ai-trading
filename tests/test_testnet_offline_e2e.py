"""End-to-end offline testnet intent staging regression; NEVER sends exchange orders."""
import tempfile
import unittest
from pathlib import Path

from agents.testnet_order_guard import TestnetOrderIntent, validate_testnet_intent
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked, submit_order
from agents.bybit_testnet_intent_ledger_v311 import TestnetIntentLedger
from agents.bybit_testnet_durable_ledger_v312 import DurableTestnetIntentLedger

SETTINGS = {
    "SPACE_BAR_ENABLE_TESTNET_ORDERS": "true",
    "SPACE_BAR_CONFIRM_TESTNET_ONLY": "true",
    "SPACE_BAR_EXCHANGE_ENV": "testnet",
    "SPACE_BAR_BYBIT_BASE_URL": "https://api-testnet.bybit.com",
}


def payload(client_id="spacebar-e2e-0001"):
    return {
        "symbol": "BTCUSDT", "side": "Sell", "orderType": "Limit",
        "qty": "0.001", "price": "50000", "reduceOnly": True,
        "clientOrderId": client_id,
    }


class TestOfflineEndToEnd(unittest.TestCase):
    def test_guard_memory_ledger_and_durable_ledger_all_remain_offline(self):
        validate_testnet_intent(TestnetOrderIntent("BTCUSDT", "Sell", "0.001"), settings=SETTINGS)
        mem = TestnetIntentLedger()
        staged = mem.stage(payload(), dry_run=True)
        self.assertEqual(staged["status"], "STAGED_NOT_SENT")
        self.assertFalse(staged["network_enabled"])
        with self.assertRaisesRegex(OrderBlocked, "DUPLICATE_CLIENT_ID"):
            mem.stage(payload(), dry_run=True)
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "intents.sqlite3"
            durable = DurableTestnetIntentLedger(db)
            try:
                result = durable.stage(payload(), dry_run=True)
                self.assertEqual(result["status"], "STAGED_NOT_SENT")
                self.assertFalse(result["orders_enabled"])
                self.assertFalse(result["network_enabled"])
            finally:
                durable.close()
            reopened = DurableTestnetIntentLedger(db)
            try:
                with self.assertRaisesRegex(OrderBlocked, "DUPLICATE_CLIENT_ID"):
                    reopened.stage(payload(), dry_run=True)
            finally:
                reopened.close()
        with self.assertRaisesRegex(OrderBlocked, "ORDER_DISPATCH_DISABLED"):
            submit_order(payload())

    def test_guard_acceptance_does_not_override_v310_reduce_only(self):
        validate_testnet_intent(TestnetOrderIntent("BTCUSDT", "Sell", "0.001"), settings=SETTINGS)
        mem = TestnetIntentLedger()
        with self.assertRaises(OrderBlocked):
            mem.stage({**payload(), "reduceOnly": False}, dry_run=True)
        self.assertEqual(mem.lookup(payload()["clientOrderId"])["status"], "NOT_STAGED")


if __name__ == "__main__":
    unittest.main()
