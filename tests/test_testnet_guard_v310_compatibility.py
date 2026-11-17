"""Offline compatibility tests between preliminary guard and V310 dry-run.

No HTTP, credentials or order submission is performed.
"""
import unittest

from agents.testnet_order_guard import TestnetOrderIntent, validate_testnet_intent
from agents.bybit_testnet_order_dryrun_v310 import (
    OrderBlocked as DryRunBlocked,
    prepare_testnet_order,
    submit_order,
)

SAFE = {
    "SPACE_BAR_ENABLE_TESTNET_ORDERS": "true",
    "SPACE_BAR_CONFIRM_TESTNET_ONLY": "true",
    "SPACE_BAR_EXCHANGE_ENV": "testnet",
    "SPACE_BAR_BYBIT_BASE_URL": "https://api-testnet.bybit.com",
}


class TestGuardV310Compatibility(unittest.TestCase):
    def test_matching_intent_remains_offline(self):
        validate_testnet_intent(TestnetOrderIntent("BTCUSDT", "Sell", "0.001"), settings=SAFE)
        preview = prepare_testnet_order({
            "symbol": "BTCUSDT", "side": "Sell", "orderType": "Limit",
            "qty": "0.001", "price": "50000", "reduceOnly": True,
            "clientOrderId": "spacebar-test-0001",
        }, dry_run=True)
        self.assertEqual(preview["status"], "VALIDATED_NOT_SENT")
        self.assertFalse(preview["network_enabled"])
        self.assertFalse(preview["orders_enabled"])
        self.assertFalse(preview["live_trading_approved"])

    def test_v310_dispatch_is_disabled_even_after_guard_acceptance(self):
        validate_testnet_intent(TestnetOrderIntent("BTCUSDT", "Sell", "0.001"), settings=SAFE)
        with self.assertRaisesRegex(DryRunBlocked, "ORDER_DISPATCH_DISABLED"):
            submit_order()

    def test_v310_rejects_non_reduce_only_even_with_guard_approval(self):
        validate_testnet_intent(TestnetOrderIntent("BTCUSDT", "Buy", "0.001"), settings=SAFE)
        with self.assertRaises(DryRunBlocked):
            prepare_testnet_order({
                "symbol": "BTCUSDT", "side": "Buy", "orderType": "Limit",
                "qty": "0.001", "price": "50000", "reduceOnly": False,
                "clientOrderId": "spacebar-test-0002",
            }, dry_run=True)


if __name__ == "__main__":
    unittest.main()
