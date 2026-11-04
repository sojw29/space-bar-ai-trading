"""Offline testnet order intent ledger. No HTTP, keys, or order dispatch."""
import hashlib
import json
from agents.bybit_testnet_order_dryrun_v310 import prepare_testnet_order, OrderBlocked

class TestnetIntentLedger:
    """In-memory fail-closed idempotency guard for validated dry-run intents.

    Does not claim cross-process durability; restart loses this in-memory state.
    """
    def __init__(self):
        self._seen = {}

    def stage(self, intent, *, dry_run=False):
        preview = prepare_testnet_order(intent, dry_run=dry_run)
        key = preview["payload"]["orderLinkId"]
        digest = preview["payload_sha256"]
        if key in self._seen:
            if self._seen[key] != digest:
                raise OrderBlocked("CLIENT_ID_CONFLICT")
            raise OrderBlocked("DUPLICATE_CLIENT_ID")
        self._seen[key] = digest
        return {
            "status": "STAGED_NOT_SENT",
            "client_order_id": key,
            "payload_sha256": digest,
            "environment": "TESTNET_ONLY",
            "orders_enabled": False,
            "network_enabled": False,
            "live_trading_approved": False,
        }

    def lookup(self, client_order_id):
        """Local staging record only, never an exchange order-status lookup."""
        if type(client_order_id) is not str:
            raise OrderBlocked("INVALID_CLIENT_ID")
        digest = self._seen.get(client_order_id)
        return {"status": "STAGED_NOT_SENT", "payload_sha256": digest} if digest else {"status": "NOT_STAGED"}
