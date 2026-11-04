import unittest
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked
from agents.bybit_testnet_readonly_status_v313 import parse_testnet_order_status as parse

ID="spacebar-test-0001"
def response(orders):
    return {"retCode":0,"result":{"category":"linear","list":orders}}
def order(status="New"):
    return {"orderLinkId":ID,"symbol":"BTCUSDT","orderStatus":status}
def check(data):
    return parse(data,expected_client_order_id=ID,expected_symbol="BTCUSDT")

class ReadonlyStatusTests(unittest.TestCase):
    def test_new_and_filled(self):
        for status in ("New","PartiallyFilled","Filled","Cancelled","Rejected"):
            with self.subTest(status=status):
                out=check(response([order(status)]))
                self.assertEqual(out["status"],status)
                self.assertFalse(out["orders_enabled"])
                self.assertFalse(out["network_enabled"])
    def test_empty_is_unknown_not_absent(self):
        self.assertEqual(check(response([]))["status"],"UNKNOWN_NOT_CONFIRMED")
    def test_fail_closed(self):
        bad=[{"retCode":10001,"result":{"category":"linear","list":[]}},
             response([order(),order()]),response([{"orderLinkId":"other-0001","symbol":"BTCUSDT","orderStatus":"New"}]),
             response([{"orderLinkId":ID,"symbol":"ETHUSDT","orderStatus":"New"}]),
             response([order("Unexpected")]),{"retCode":0,"result":{"category":"spot","list":[]}},
             {"retCode":True,"result":{"category":"linear","list":[]}}]
        for item in bad:
            with self.subTest(item=item),self.assertRaises(OrderBlocked):
                check(item)
if __name__=="__main__":
    unittest.main()
