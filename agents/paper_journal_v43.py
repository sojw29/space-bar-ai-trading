"""V43 opt-in append-only research paper journal.

SQLite stores simulated snapshots and simulated trade events. A new random
session is created on EVERY process launch. Prior sessions are never resumed
into a position. Hash chaining detects accidental changes to persisted rows;
it is not tamper-proof against DB rewriting and does not verify profits.
No network, account connection, orders, or trading capability.
"""
import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64
DDL = """
CREATE TABLE IF NOT EXISTS paper_sessions (
 session_id TEXT PRIMARY KEY, created_utc TEXT NOT NULL,
 mode TEXT NOT NULL CHECK(mode='SIMULATED_ONLY')
);
CREATE TABLE IF NOT EXISTS paper_events (
 session_id TEXT NOT NULL, seq INTEGER NOT NULL,
 recorded_utc TEXT NOT NULL, kind TEXT NOT NULL,
 payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
 entry_hash TEXT NOT NULL,
 PRIMARY KEY(session_id,seq),
 FOREIGN KEY(session_id) REFERENCES paper_sessions(session_id)
);
"""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":"))


def event_hash(session_id, seq, recorded_utc, kind, payload_json, previous):
    message = canonical([session_id, seq, recorded_utc, kind, payload_json, previous])
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


def verify_session(db_path, session_id):
    """Read-only integrity validation for one historical simulated session."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5) as conn:
        rows = conn.execute(
            "SELECT seq,recorded_utc,kind,payload_json,previous_hash,entry_hash "
            "FROM paper_events WHERE session_id=? ORDER BY seq", (session_id,)).fetchall()
    previous = GENESIS
    for expected, (seq, timestamp, kind, payload, previous_hash, digest) in enumerate(rows, 1):
        if seq != expected or previous_hash != previous:
            raise ValueError("Paper journal sequence/hash chain mismatch")
        if event_hash(session_id, seq, timestamp, kind, payload, previous) != digest:
            raise ValueError("Paper journal digest mismatch")
        previous = digest
    return {"session_id": session_id, "entries": len(rows),
            "last_hash": previous, "valid": True, "mode": "SIMULATED_ONLY"}


class PaperJournal:
    def __init__(self, path, *, clock=None, session_id=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or str(uuid.uuid4())
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self.lock = threading.Lock()
        with sqlite3.connect(str(self.path), timeout=10) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(DDL)
            conn.execute(
                "INSERT INTO paper_sessions(session_id,created_utc,mode) VALUES(?,?,?)",
                (self.session_id, self.clock(), "SIMULATED_ONLY"))

    def append(self, kind, payload):
        if kind not in ("paper_snapshot", "feed_halt"):
            raise ValueError("Unsupported paper journal event")
        if not isinstance(payload, dict) or (payload.get("paper_only") is not True or
                                            payload.get("orders_enabled") is not False or
                                            payload.get("live_trading_approved") is not False):
            raise ValueError("Unsafe paper record")
        serialized = canonical(payload)
        if len(serialized) > 1_000_000:
            raise ValueError("Paper journal event too large")
        recorded = self.clock()
        with self.lock, sqlite3.connect(str(self.path), timeout=10) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            last = conn.execute(
                "SELECT seq,entry_hash FROM paper_events "
                "WHERE session_id=? ORDER BY seq DESC LIMIT 1",
                (self.session_id,)).fetchone()
            seq, previous = (last[0]+1, last[1]) if last else (1, GENESIS)
            digest = event_hash(self.session_id, seq, recorded, kind, serialized, previous)
            conn.execute(
                "INSERT INTO paper_events(session_id,seq,recorded_utc,kind,"
                "payload_json,previous_hash,entry_hash) VALUES(?,?,?,?,?,?,?)",
                (self.session_id, seq, recorded, kind, serialized, previous, digest))
        return {"session_id": self.session_id, "seq": seq, "sha256": digest}


def session_events(db_path, session_id, limit=100):
    """Read-only history retrieval; does not restore/activate past positions."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be in 1..500")
    verify_session(db_path, session_id)
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        rows = conn.execute(
            "SELECT seq,recorded_utc,kind,payload_json FROM paper_events "
            "WHERE session_id=? ORDER BY seq DESC LIMIT ?", (session_id, limit)).fetchall()
    return [{"seq": seq, "recorded_utc": recorded, "kind": kind,
             "paper_data": json.loads(data)} for seq, recorded, kind, data in rows]
