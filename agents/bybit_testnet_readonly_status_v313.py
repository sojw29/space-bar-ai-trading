"""Fail-closed Bybit TESTNET order status response parser (offline only).

No HTTP transport, credentials, or order dispatch. Accepts injected response data.
"""
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked
import re

ORDER_STATUSES = frozenset({"Created", "New", "PartiallyFilled", "Filled", "Cancelled", "Rejected", "PartiallyFilledCanceled", "Untriggered", "Triggered", "Deactivated"})
LINK_ID = re.compile(r"^[A-Za-z0-9_-]{8,36}$")

def parse_testnet_order_status(response, *, expected_client_order_id, expected_symbol):
    """Parse an externally supplied V5 /v5/order/realtime JSON response.

    An empty list is UNKNOWN, not evidence that an order was never placed.
    """
    if type(expected_client_order_id) is not str or not LINK_ID.fullmatch(expected_client_order_id):
        raise OrderBlocked("INVALID_CLIENT_ID")
    if type(expected_symbol) is not str or expected_symbol not in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        raise OrderBlocked("INVALID_SYMBOL")
    if not isinstance(response, dict) or type(response.get("retCode")) is not int or response["retCode"] != 0:
        raise OrderBlocked("EXCHANGE_RESPONSE_ERROR")
    result = response.get("result")
    if not isinstance(result, dict) or result.get("category") != "linear":
        raise OrderBlocked("INVALID_CATEGORY")
    orders = result.get("list")
    if not isinstance(orders, list) or len(orders) > 1:
        raise OrderBlocked("AMBIGUOUS_ORDER_RESPONSE")
    if not orders:
        return {"status":"UNKNOWN_NOT_CONFIRMED","client_order_id":expected_client_order_id,
                "environment":"TESTNET_ONLY","orders_enabled":False,"network_enabled":False}
    order = orders[0]
    if not isinstance(order, dict) or order.get("orderLinkId") != expected_client_order_id or order.get("symbol") != expected_symbol:
        raise OrderBlocked("ORDER_IDENTITY_MISMATCH")
    status = order.get("orderStatus")
    if type(status) is not str or status not in ORDER_STATUSES:
        raise OrderBlocked("UNKNOWN_ORDER_STATUS")
    return {"status":status,"client_order_id":expected_client_order_id,"symbol":expected_symbol,
            "environment":"TESTNET_ONLY","orders_enabled":False,"network_enabled":False}
