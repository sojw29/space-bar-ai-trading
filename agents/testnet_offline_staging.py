"""Offline-only preflight + durable intent staging, never an exchange executor.

The caller must provide an already-open V312 ledger on a trusted local filesystem.
No HTTP, credentials, dashboard hooks or order submission exist in this module.
"""
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
