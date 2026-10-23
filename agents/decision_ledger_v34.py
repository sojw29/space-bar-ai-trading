"""V34 immutable research decision ledger (SQLite, standard library).

Opt-in local observation snapshots only. Replaying historical data is not
independent forward testing. No trading, network, or broker integrations.
"""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import agent_events_v27 as events
from dashboard_api_v28 import DEFAULT_HISTORY, load_candles

DDL = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    candle_utc TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    recorded_utc TEXT NOT NULL,
    UNIQUE(symbol, timeframe, candle_utc)
);
"""


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def validate_envelope(envelope):
    if envelope.get("paper_only") is not True or envelope.get("orders_enabled") is not False:
        raise ValueError("Only paper-only, order-disabled envelopes are allowed")
    if envelope.get("live_trading_approved") is not False or envelope.get("independent_oos_verified") is not False:
        raise ValueError("Unsupported research safety flags")
    if envelope.get("event_schema_version") != events.VERSION:
        raise ValueError("Unsupported event schema version")
    timestamp = envelope.get("observed_candle_utc")
    if not isinstance(timestamp, str) or not timestamp:
        raise ValueError("Missing candle timestamp")
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Candle timestamp must have a timezone")
    if parsed > datetime.now(timezone.utc):
        raise ValueError("Future candle timestamp")
    agent_events = envelope.get("events")
    if not isinstance(agent_events, list) or len(agent_events) != 7:
        raise ValueError("Expected six agents and COMMANDER")
    names = [e.get("agent_id") for e in agent_events]
    if set(names) != set(("COMMANDER",) + events.v26.AGENTS) or len(set(names)) != 7:
        raise ValueError("Invalid agent set")
    for item in agent_events:
        if item.get("decision") not in events.v26.DECISIONS:
            raise ValueError("Invalid decision")
        if item.get("observed_candle_utc") != timestamp:
            raise ValueError("Mixed observation timestamps")
    commander = next(e for e in agent_events if e["agent_id"] == "COMMANDER")
    longs = sum(e["decision"] == "LONG" for e in agent_events if e["agent_id"] != "COMMANDER")
    shorts = sum(e["decision"] == "SHORT" for e in agent_events if e["agent_id"] != "COMMANDER")
    if commander.get("long_votes") != longs or commander.get("short_votes") != shorts:
        raise ValueError("Vote count mismatch")
    veto = commander.get("risk_veto")
    if not isinstance(veto, bool):
        raise ValueError("Missing veto")
    expected = "WAIT" if veto else "LONG" if longs >= 3 and shorts == 0 else "SHORT" if shorts >= 3 and longs == 0 else "WAIT"
    if commander["decision"] != expected:
        raise ValueError("Commander decision inconsistent with votes")
    if envelope.get("symbol") != "BTCUSDT" or envelope.get("timeframe") != "5m":
        raise ValueError("Unsupported symbol/timeframe")


def record(db_path, envelope):
    """Return 'inserted' or 'unchanged'. Reject conflicting replay snapshots."""
    validate_envelope(envelope)
    payload = _canonical(envelope)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path), timeout=10) as conn:
        conn.execute(DDL)
        key = (envelope["symbol"], envelope["timeframe"], envelope["observed_candle_utc"])
        previous = conn.execute(
            "SELECT payload_sha256 FROM decisions WHERE symbol=? AND timeframe=? AND candle_utc=?",
            key).fetchone()
        if previous:
            if previous[0] != digest:
                raise ValueError("Immutable ledger conflict: same candle, changed snapshot")
            return "unchanged"
        conn.execute(
            "INSERT INTO decisions(symbol,timeframe,candle_utc,source,payload_sha256,payload_json,recorded_utc) "
            "VALUES(?,?,?,?,?,?,?)",
            (*key, "historical_csv_snapshot", digest, payload,
             datetime.now(timezone.utc).isoformat()))
        return "inserted"


def read_recent(db_path, limit=20):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    db_path = Path(db_path)
    if not db_path.is_file():
        return []
    with sqlite3.connect(str(db_path), timeout=10) as conn:
        entries = conn.execute(
            "SELECT candle_utc,source,payload_sha256,payload_json,recorded_utc "
            "FROM decisions ORDER BY candle_utc DESC LIMIT ?", (limit,)).fetchall()
    return [
        {"candle_utc": ts, "source": source, "sha256": digest,
         "event_envelope": json.loads(payload), "recorded_utc": logged}
        for ts, source, digest, payload, logged in entries
    ]


def main():
    parser = argparse.ArgumentParser(description="Opt-in V34 immutable paper research ledger")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--db", type=Path, default=Path("reports/v34/research_decisions.sqlite3"))
    parser.add_argument("--recent", type=int, default=0,
                        help="Read last N entries without collecting a new snapshot (1..100)")
    args = parser.parse_args()
    if args.recent:
        print(json.dumps(read_recent(args.db, args.recent), ensure_ascii=False, indent=2))
        return
    envelope = events.analyze_and_emit(load_candles(args.history))
    outcome = record(args.db, envelope)
    print(json.dumps({"record_status": outcome, "candle_utc": envelope["observed_candle_utc"],
                      "source": "historical_csv_snapshot", "paper_only": True,
                      "independent_oos_verified": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
