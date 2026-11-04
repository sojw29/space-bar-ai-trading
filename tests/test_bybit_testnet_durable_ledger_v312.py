import tempfile
import unittest
from pathlib import Path
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked
from agents.bybit_testnet_durable_ledger_v312 import DurableTestnetIntentLedger

def intent():
    return {"symbol":"BTCUSDT","side":"Sell","orderType":"Limit","qty":"0.001",
            "price":"50000","reduceOnly":True,"clientOrderId":"spacebar-test-0001"}

class DurableLedgerTests(unittest.TestCase):
    def test_restart_persists_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"orders.sqlite3"
            a=DurableTestnetIntentLedger(path)
            result=a.stage(intent(),dry_run=True)
            self.assertFalse(result["network_enabled"])
            a.close()
            b=DurableTestnetIntentLedger(path)
            self.assertEqual(b.lookup(intent()["clientOrderId"])["status"],"STAGED_NOT_SENT")
            with self.assertRaisesRegex(OrderBlocked,"DUPLICATE_CLIENT_ID"):
                b.stage(intent(),dry_run=True)
            with self.assertRaisesRegex(OrderBlocked,"CLIENT_ID_CONFLICT"):
                b.stage({**intent(),"price":"40000"},dry_run=True)
            b.close()
    def test_invalid_does_not_reserve(self):
        with tempfile.TemporaryDirectory() as d:
            a=DurableTestnetIntentLedger(Path(d)/"orders.db")
            with self.assertRaises(OrderBlocked):
                a.stage({**intent(),"reduceOnly":False},dry_run=True)
            with self.assertRaises(OrderBlocked):
                a.stage(intent())
            self.assertEqual(a.lookup(intent()["clientOrderId"])["status"],"NOT_STAGED")
            a.stage(intent(),dry_run=True)
            a.close()
    def test_second_connection_cannot_reuse_id(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"orders.db"
            a=DurableTestnetIntentLedger(path)
            b=DurableTestnetIntentLedger(path)
            a.stage(intent(),dry_run=True)
            with self.assertRaisesRegex(OrderBlocked,"DUPLICATE_CLIENT_ID"):
                b.stage(intent(),dry_run=True)
            a.close()
            b.close()
if __name__=="__main__":
    unittest.main()
