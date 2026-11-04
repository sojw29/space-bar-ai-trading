"""Persistent OFFLINE Bybit testnet intent staging; never submits orders."""
import sqlite3
from pathlib import Path
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked, prepare_testnet_order

class DurableTestnetIntentLedger:
    """SQLite transaction-backed uniqueness across restarts and concurrent processes.

    File must be on a trusted local filesystem. This does not verify exchange state.
    """
    def __init__(self, path):
        self.path = Path(path)
        if str(self.path) == ":memory:":
            raise OrderBlocked("PERSISTENT_PATH_REQUIRED")
        if self.path.is_symlink() or not self.path.parent.is_dir():
            raise OrderBlocked("UNSAFE_LEDGER_PATH")
        self.db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        try:
            self.db.execute("PRAGMA busy_timeout=5000")
            self.db.execute("CREATE TABLE IF NOT EXISTS intents (client_id TEXT PRIMARY KEY NOT NULL, payload_sha256 TEXT NOT NULL)")
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def stage(self, intent, *, dry_run=False):
        preview = prepare_testnet_order(intent, dry_run=dry_run)
        key = preview["payload"]["orderLinkId"]
        digest = preview["payload_sha256"]
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT payload_sha256 FROM intents WHERE client_id=?", (key,)).fetchone()
            if row is not None:
                raise OrderBlocked("DUPLICATE_CLIENT_ID" if row[0] == digest else "CLIENT_ID_CONFLICT")
            self.db.execute("INSERT INTO intents(client_id,payload_sha256) VALUES(?,?)", (key,digest))
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        return {"status":"STAGED_NOT_SENT","client_order_id":key,"payload_sha256":digest,
                "environment":"TESTNET_ONLY","orders_enabled":False,"network_enabled":False,
                "live_trading_approved":False}

    def lookup(self, client_order_id):
        if type(client_order_id) is not str:
            raise OrderBlocked("INVALID_CLIENT_ID")
        row = self.db.execute("SELECT payload_sha256 FROM intents WHERE client_id=?", (client_order_id,)).fetchone()
        return {"status":"STAGED_NOT_SENT","payload_sha256":row[0]} if row else {"status":"NOT_STAGED"}
