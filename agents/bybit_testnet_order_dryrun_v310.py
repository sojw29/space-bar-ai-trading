"""Bybit V5 TESTNET order intent validator. OFFLINE ONLY: no network, keys or order dispatch.

This is a safe staging boundary, NOT an enabled order executor.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

class OrderBlocked(ValueError):
    pass

_ALLOWED_SYMBOLS = frozenset({"BTCUSDT", "ETHUSDT", "SOLUSDT"})
_ALLOWED_KEYS = frozenset({"symbol", "side", "orderType", "qty", "price", "reduceOnly", "clientOrderId"})
_ID = re.compile(r"^[A-Za-z0-9_-]{8,36}$")

def _positive_decimal(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        raise OrderBlocked("INVALID_" + field)
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise OrderBlocked("INVALID_" + field) from None
    if not number.is_finite() or number <= 0:
        raise OrderBlocked("INVALID_" + field)
    return number

def prepare_testnet_order(intent, *, dry_run=False):
    """Validate and serialize an *unsubmitted* order for testnet review.

    Requires explicit dry_run=True. No credentials, HTTP transport, or live URL.
    Restricts symbols, size, notional, limit-only, reduce-only and unique ID format.
    """
    if dry_run is not True:
        raise OrderBlocked("DRY_RUN_REQUIRED")
    if not isinstance(intent, dict) or set(intent) != _ALLOWED_KEYS:
        raise OrderBlocked("INVALID_FIELDS")
    if intent["symbol"] not in _ALLOWED_SYMBOLS:
        raise OrderBlocked("SYMBOL_NOT_ALLOWED")
    if intent["side"] not in ("Buy", "Sell") or intent["orderType"] != "Limit":
        raise OrderBlocked("LIMIT_ONLY")
    if intent["reduceOnly"] is not True:
        raise OrderBlocked("REDUCE_ONLY_REQUIRED")
    if not isinstance(intent["clientOrderId"], str) or not _ID.fullmatch(intent["clientOrderId"]):
        raise OrderBlocked("INVALID_CLIENT_ID")
    qty = _positive_decimal(intent["qty"], "QTY")
    price = _positive_decimal(intent["price"], "PRICE")
    if qty > Decimal("1") or qty * price > Decimal("100"):
        raise OrderBlocked("SIZE_LIMIT")
    payload = {
        "category": "linear", "symbol": intent["symbol"],
        "side": intent["side"], "orderType": "Limit",
        "qty": str(qty), "price": str(price),
        "timeInForce": "PostOnly", "reduceOnly": True,
        "orderLinkId": intent["clientOrderId"],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "version": "BYBIT_TESTNET_ORDER_DRY_RUN_V1",
        "environment": "TESTNET_ONLY", "endpoint_path": "/v5/order/create",
        "status": "VALIDATED_NOT_SENT", "payload": payload,
        "payload_sha256": hashlib.sha256(encoded).hexdigest(),
        "network_enabled": False, "credentials_required": False,
        "orders_enabled": False, "live_trading_approved": False,
    }

def submit_order(*args, **kwargs):
    """No dispatch implementation is present by design."""
    raise OrderBlocked("ORDER_DISPATCH_DISABLED")
