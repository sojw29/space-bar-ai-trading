"""Fail-closed policy for future Bybit testnet order integration.

This module does not submit orders or read credentials. Importing it is safe.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Mapping


class OrderBlocked(ValueError):
    """An order was rejected before reaching any exchange adapter."""


@dataclass(frozen=True)
class TestnetOrderIntent:
    symbol: str
    side: str
    quantity: str


def validate_testnet_intent(
    intent: TestnetOrderIntent,
    *,
    settings: Mapping[str, str],
) -> None:
    """Validate an intent without executing it.

    Both explicit switches are required; production endpoints are never allowed.
    This is only a preliminary gate, not authorization to send an order.
    """
    if not isinstance(settings, Mapping):
        raise OrderBlocked("Invalid testnet settings")
    if not isinstance(intent, TestnetOrderIntent):
        raise OrderBlocked("Invalid testnet order intent")
    if settings.get("SPACE_BAR_ENABLE_TESTNET_ORDERS") != "true":
        raise OrderBlocked("Testnet orders disabled by default")
    if settings.get("SPACE_BAR_CONFIRM_TESTNET_ONLY") != "true":
        raise OrderBlocked("Explicit testnet-only confirmation missing")
    if settings.get("SPACE_BAR_EXCHANGE_ENV") != "testnet":
        raise OrderBlocked("Only testnet environment is permitted")
    if settings.get("SPACE_BAR_BYBIT_BASE_URL") != "https://api-testnet.bybit.com":
        raise OrderBlocked("Non-testnet or unknown Bybit endpoint")
    if intent.symbol not in {"BTCUSDT", "ETHUSDT", "SOLUSDT"}:
        raise OrderBlocked("Symbol is not allowlisted")
    if intent.side not in {"Buy", "Sell"}:
        raise OrderBlocked("Invalid side")
    if type(intent.quantity) is not str or re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', intent.quantity) is None:
        raise OrderBlocked('Invalid quantity format')
    try:
        qty = Decimal(intent.quantity)
    except (InvalidOperation, TypeError, ValueError):
        raise OrderBlocked("Invalid quantity") from None
    if not qty.is_finite() or qty <= 0 or qty > Decimal("0.01"):
        raise OrderBlocked("Quantity outside preliminary safety limit")
