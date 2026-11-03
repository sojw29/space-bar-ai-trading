"""Offline safety contract tests: no network and no exchange orders."""
import unittest
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked, prepare_testnet_order, submit_order

def intent():
    return {"symbol":"BTCUSDT","side":"Sell","orderType":"Limit",
            "qty":"0.001","price":"50000","reduceOnly":True,
            "clientOrderId":"spacebar-test-0001"}

class TestBybitTestnetDryRun(unittest.TestCase):
    def test_requires_explicit_dry_run(self):
        with self.assertRaises(OrderBlocked):
            prepare_testnet_order(intent())
        with self.assertRaises(OrderBlocked):
            prepare_testnet_order(intent(),dry_run=1)
    def test_valid_preview_is_never_sent(self):
        out=prepare_testnet_order(intent(),dry_run=True)
        self.assertEqual(out["status"],"VALIDATED_NOT_SENT")
        self.assertEqual(out["environment"],"TESTNET_ONLY")
        self.assertFalse(out["network_enabled"])
        self.assertFalse(out["orders_enabled"])
        self.assertFalse(out["live_trading_approved"])
        self.assertTrue(out["payload"]["reduceOnly"])
        self.assertEqual(out["payload"]["timeInForce"],"PostOnly")
    def test_disallowed_fields_and_market_orders(self):
        for change in ({"apiKey":"secret"},{"orderType":"Market"},{"reduceOnly":False},
                       {"symbol":"DOGEUSDT"},{"side":"SHORT"},{"qty":"NaN"},
                       {"qty":"-1"},{"price":"0"},{"clientOrderId":"bad"}):
            with self.subTest(change=change),self.assertRaises(OrderBlocked):
                prepare_testnet_order({**intent(),**change},dry_run=True)
    def test_size_limits(self):
        for change in ({"qty":"2"},{"price":"200000"}):
            with self.subTest(change=change),self.assertRaises(OrderBlocked):
                prepare_testnet_order({**intent(),**change},dry_run=True)
    def test_no_dispatch(self):
        with self.assertRaisesRegex(OrderBlocked,"ORDER_DISPATCH_DISABLED"):
            submit_order(intent())
if __name__=="__main__":
    unittest.main()
