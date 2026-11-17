"""Offline-only tests for composed testnet staging preflight."""
import unittest
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked
from agents.testnet_order_guard import OrderBlocked as GuardBlocked
from agents.testnet_staging_preflight import preflight_testnet_staging

SAFE = {
    "SPACE_BAR_ENABLE_TESTNET_ORDERS": "true",
    "SPACE_BAR_CONFIRM_TESTNET_ONLY": "true",
    "SPACE_BAR_EXCHANGE_ENV": "testnet",
    "SPACE_BAR_BYBIT_BASE_URL": "https://api-testnet.bybit.com",
}


def intent():
    return {
        "symbol": "BTCUSDT", "side": "Sell", "orderType": "Limit",
        "qty": "0.001", "price": "50000", "reduceOnly": True,
        "clientOrderId": "spacebar-preflight-001",
    }


class TestPreflight(unittest.TestCase):
    def test_valid_preview_never_sent(self):
        result = preflight_testnet_staging(intent(), settings=SAFE, dry_run=True)
        self.assertEqual(result["status"], "VALIDATED_NOT_SENT")
        self.assertFalse(result["network_enabled"])
        self.assertFalse(result["orders_enabled"])

    def test_dry_run_required(self):
        for flag in (False, None, 1, "true"):
            with self.subTest(flag=flag), self.assertRaises(OrderBlocked):
                preflight_testnet_staging(intent(), settings=SAFE, dry_run=flag)

    def test_guard_blocks_disabled_settings(self):
        with self.assertRaises(GuardBlocked):
            preflight_testnet_staging(intent(), settings={}, dry_run=True)

    def test_v310_blocks_non_reduce_only(self):
        with self.assertRaises(OrderBlocked):
            preflight_testnet_staging({**intent(), "reduceOnly": False}, settings=SAFE, dry_run=True)

    def test_guard_blocks_quantity_above_preliminary_cap(self):
        with self.assertRaises(GuardBlocked):
            preflight_testnet_staging({**intent(), "qty": "0.02", "price": "100"}, settings=SAFE, dry_run=True)


if __name__ == "__main__":
    unittest.main()
