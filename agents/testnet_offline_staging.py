"""Offline-only preflight + durable intent staging, never an exchange executor.

The caller must provide an already-open V312 ledger on a trusted local filesystem.
No HTTP, credentials, dashboard hooks or order submission exist in this module.
"""
import sqlite3

from agents.testnet_staging_preflight import preflight_testnet_staging
from agents.bybit_testnet_durable_ledger_v312 import DurableTestnetIntentLedger
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked


def stage_preflighted_testnet_intent(intent, *, settings, ledger, dry_run=False):
    """Validate through the preliminary guard and V310 before V312 staging."""
    if dry_run is not True:
        raise OrderBlocked("DRY_RUN_REQUIRED")
    if not isinstance(ledger, DurableTestnetIntentLedger):
        raise OrderBlocked("DURABLE_LEDGER_REQUIRED")
    preflight_testnet_staging(intent, settings=settings, dry_run=True)
    result = ledger.stage(intent, dry_run=True)
    if result["status"] != "STAGED_NOT_SENT" or result["network_enabled"] is not False or result["orders_enabled"] is not False:
        raise OrderBlocked("UNSAFE_STAGE_RESULT")
    return result


def stage_preflighted_testnet_intent_status(intent, *, settings, ledger, dry_run=False):
    """Return a bounded, non-sensitive offline staging status for a UI.

    Only known validation and SQLite errors are mapped. No network or orders.
    Never expose SQL exception messages, intent payloads, or configuration.
    """
    try:
        result = stage_preflighted_testnet_intent(
            intent, settings=settings, ledger=ledger, dry_run=dry_run
        )
    except sqlite3.Error:
        return {"status": "BLOCKED", "reason": "LEDGER_UNAVAILABLE", "orders_enabled": False, "network_enabled": False}
    except OrderBlocked:
        return {"status": "BLOCKED", "reason": "ORDER_VALIDATION_BLOCKED", "orders_enabled": False, "network_enabled": False}
    except Exception as exc:
        # Preliminary guard has a distinct OrderBlocked class; do not leak its
        # raw validation details into a UI or accidentally mark staging complete.
        from agents.testnet_order_guard import OrderBlocked as PreliminaryOrderBlocked
        if isinstance(exc, PreliminaryOrderBlocked):
            return {"status": "BLOCKED", "reason": "PREFLIGHT_BLOCKED", "orders_enabled": False, "network_enabled": False}
        raise
    return {
        "status": "STAGED_NOT_SENT",
        "reason": "OFFLINE_ONLY",
        "orders_enabled": False,
        "network_enabled": False,
        "client_order_id": result["client_order_id"],
    }
