import unittest
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked
from agents.bybit_testnet_intent_ledger_v311 import TestnetIntentLedger

def intent():
    return {"symbol":"BTCUSDT","side":"Sell","orderType":"Limit",
            "qty":"0.001","price":"50000","reduceOnly":True,
            "clientOrderId":"spacebar-test-0001"}

class LedgerTests(unittest.TestCase):
    def test_stage_is_offline_only(self):
        ledger=TestnetIntentLedger()
        out=ledger.stage(intent(),dry_run=True)
        self.assertEqual(out["status"],"STAGED_NOT_SENT")
        self.assertFalse(out["network_enabled"])
        self.assertFalse(out["orders_enabled"])
        self.assertEqual(ledger.lookup(intent()["clientOrderId"])["status"],"STAGED_NOT_SENT")
    def test_duplicate_is_blocked(self):
        ledger=TestnetIntentLedger()
        ledger.stage(intent(),dry_run=True)
        with self.assertRaisesRegex(OrderBlocked,"DUPLICATE_CLIENT_ID"):
            ledger.stage(intent(),dry_run=True)
        with self.assertRaisesRegex(OrderBlocked,"CLIENT_ID_CONFLICT"):
            ledger.stage({**intent(),"price":"40000"},dry_run=True)
    def test_invalid_does_not_reserve_id(self):
        ledger=TestnetIntentLedger()
        with self.assertRaises(OrderBlocked):
            ledger.stage({**intent(),"reduceOnly":False},dry_run=True)
        self.assertEqual(ledger.lookup(intent()["clientOrderId"])["status"],"NOT_STAGED")
        with self.assertRaises(OrderBlocked):
            ledger.stage(intent())
        self.assertEqual(ledger.lookup(intent()["clientOrderId"])["status"],"NOT_STAGED")
        ledger.stage(intent(),dry_run=True)
if __name__=="__main__":
    unittest.main()
