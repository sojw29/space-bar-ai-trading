"""Offline Bybit V5 testnet read-only request descriptor.

No HTTP client, API credentials, signature, or order dispatch. This module
cannot make any network request; it only validates a request specification.
"""
import re
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked

_ALLOWED_SYMBOLS = frozenset({"BTCUSDT", "ETHUSDT", "SOLUSDT"})
_ID = re.compile(r"^[A-Za-z0-9_-]{8,36}$")

def prepare_testnet_status_query(*, symbol, client_order_id, dry_run=False):
    """Return an inert read-only request descriptor, never execute it."""
    if dry_run is not True:
        raise OrderBlocked("DRY_RUN_REQUIRED")
    if type(symbol) is not str or symbol not in _ALLOWED_SYMBOLS:
        raise OrderBlocked("INVALID_SYMBOL")
    if type(client_order_id) is not str or not _ID.fullmatch(client_order_id):
        raise OrderBlocked("INVALID_CLIENT_ID")
    return {
        "version": "BYBIT_TESTNET_READONLY_QUERY_V1",
        "environment": "TESTNET_ONLY",
        "method": "GET",
        "endpoint_path": "/v5/order/realtime",
        "params": {"category": "linear", "symbol": symbol, "orderLinkId": client_order_id},
        "status": "PREPARED_NOT_SENT",
        "network_enabled": False,
        "orders_enabled": False,
        "credentials_included": False,
        "live_trading_approved": False,
        "note": "Offline descriptor only; no exchange status was queried.",
    }
