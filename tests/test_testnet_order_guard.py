"""Offline safety regression tests; no network or API credentials."""
import unittest
from agents.testnet_order_guard import OrderBlocked, TestnetOrderIntent, validate_testnet_intent

SAFE = {
    "SPACE_BAR_ENABLE_TESTNET_ORDERS": "true",
    "SPACE_BAR_CONFIRM_TESTNET_ONLY": "true",
    "SPACE_BAR_EXCHANGE_ENV": "testnet",
    "SPACE_BAR_BYBIT_BASE_URL": "https://api-testnet.bybit.com",
}
INTENT = TestnetOrderIntent("BTCUSDT", "Buy", "0.001")


class TestTestnetOrderGuard(unittest.TestCase):
    def test_disabled_by_default(self):
        with self.assertRaises(OrderBlocked):
            validate_testnet_intent(INTENT, settings={})

    def test_explicit_testnet_intent_only(self):
        validate_testnet_intent(INTENT, settings=SAFE)

    def test_every_required_setting_fails_closed(self):
        for key in SAFE:
            with self.subTest(key=key):
                settings = dict(SAFE)
                settings.pop(key)
                with self.assertRaises(OrderBlocked):
                    validate_testnet_intent(INTENT, settings=settings)

    def test_production_endpoint_rejected(self):
        settings = dict(SAFE, SPACE_BAR_BYBIT_BASE_URL="https://api.bybit.com")
        with self.assertRaises(OrderBlocked):
            validate_testnet_intent(INTENT, settings=settings)

    def test_bad_quantities_rejected(self):
        for quantity in ("0", "-1", "NaN", "Infinity", "0.011", "oops"):
            with self.subTest(quantity=quantity):
                with self.assertRaises(OrderBlocked):
                    validate_testnet_intent(TestnetOrderIntent("BTCUSDT", "Buy", quantity), settings=SAFE)

    def test_invalid_side_rejected(self):
        for side in ("BUY", "sell", "", "Hold"):
            with self.subTest(side=side):
                with self.assertRaises(OrderBlocked):
                    validate_testnet_intent(TestnetOrderIntent("BTCUSDT", side, "0.001"), settings=SAFE)

    def test_non_string_quantities_rejected(self):
        for quantity in (None, [], {}):
            with self.subTest(quantity=repr(quantity)):
                with self.assertRaises(OrderBlocked):
                    validate_testnet_intent(TestnetOrderIntent("BTCUSDT", "Buy", quantity), settings=SAFE)

    def test_quantity_boundary(self):
        validate_testnet_intent(TestnetOrderIntent("BTCUSDT", "Buy", "0.01"), settings=SAFE)
        with self.assertRaises(OrderBlocked):
            validate_testnet_intent(TestnetOrderIntent("BTCUSDT", "Buy", "0.0100000001"), settings=SAFE)

    def test_switches_must_be_exact_and_endpoint_canonical(self):
        mutations = (
            ("SPACE_BAR_ENABLE_TESTNET_ORDERS", "TRUE"),
            ("SPACE_BAR_ENABLE_TESTNET_ORDERS", "1"),
            ("SPACE_BAR_CONFIRM_TESTNET_ONLY", "True"),
            ("SPACE_BAR_EXCHANGE_ENV", "mainnet"),
            ("SPACE_BAR_BYBIT_BASE_URL", "https://api-testnet.bybit.com/"),
            ("SPACE_BAR_BYBIT_BASE_URL", "http://api-testnet.bybit.com"),
            ("SPACE_BAR_BYBIT_BASE_URL", "https://api-testnet.bybit.com.evil.example"),
        )
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                settings = dict(SAFE, **{key: value})
                with self.assertRaises(OrderBlocked):
                    validate_testnet_intent(INTENT, settings=settings)

    def test_allowed_symbols_and_sides(self):
        for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
            for side in ("Buy", "Sell"):
                with self.subTest(symbol=symbol, side=side):
                    validate_testnet_intent(TestnetOrderIntent(symbol, side, "0.001"), settings=SAFE)

    def test_unknown_symbol_rejected(self):
        with self.assertRaises(OrderBlocked):
            validate_testnet_intent(TestnetOrderIntent("DOGEUSDT", "Buy", "0.001"), settings=SAFE)


if __name__ == "__main__":
    unittest.main()
