"""Offline preflight for testnet-only *staging*, never exchange dispatch.

This adapter composes the preliminary intent gate and the existing V310-V312
validators without changing the order execution boundary.
"""
from agents.testnet_order_guard import TestnetOrderIntent, validate_testnet_intent
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked, prepare_testnet_order


def preflight_testnet_staging(intent, *, settings, dry_run=False):
    """Return a V310 preview only after the explicit preliminary gate.

    No network access, credentials, staging, or order dispatch. The returned
    payload is a review artifact and MUST NOT be treated as execution approval.
    """
    if dry_run is not True:
        raise OrderBlocked("DRY_RUN_REQUIRED")
    preview = prepare_testnet_order(intent, dry_run=True)
    payload = preview["payload"]
    validate_testnet_intent(
        TestnetOrderIntent(payload["symbol"], payload["side"], payload["qty"]),
        settings=settings,
    )
    return preview
