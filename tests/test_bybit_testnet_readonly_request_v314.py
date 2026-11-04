import unittest
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked
from agents.bybit_testnet_readonly_request_v314 import prepare_testnet_status_query as prepare

ID="spacebar-test-0001"
class TestReadOnlyQuery(unittest.TestCase):
    def test_safe_descriptor(self):
        q=prepare(symbol="BTCUSDT",client_order_id=ID,dry_run=True)
        self.assertEqual(q["method"],"GET")
        self.assertEqual(q["endpoint_path"],"/v5/order/realtime")
        self.assertEqual(q["params"]["orderLinkId"],ID)
        self.assertEqual(q["status"],"PREPARED_NOT_SENT")
        self.assertFalse(q["network_enabled"])
        self.assertFalse(q["orders_enabled"])
        self.assertFalse(q["credentials_included"])
    def test_fail_closed(self):
        cases=[{"symbol":"DOGEUSDT"},{"symbol":[]},{"symbol":None},
               {"client_order_id":"bad"},{"client_order_id":[]},
               {"client_order_id":"a"*37}]
        for change in cases:
            with self.subTest(change=change),self.assertRaises(OrderBlocked):
                prepare(**{"symbol":"BTCUSDT","client_order_id":ID,**change},dry_run=True)
        for flag in (False,1,None):
            with self.subTest(flag=flag),self.assertRaises(OrderBlocked):
                prepare(symbol="BTCUSDT",client_order_id=ID,dry_run=flag)
if __name__=="__main__":
    unittest.main()
