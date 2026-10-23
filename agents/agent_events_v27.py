"""V27: deterministic agent event protocol for future dashboard/3D clients.

Transforms V26 output into transport-neutral JSON events. No broker or orders.
"""
import json
from datetime import datetime, timezone

import multi_agent_v26 as v26

VERSION = "27.0"
STATUSES = {"LONG": "bullish", "SHORT": "bearish", "WAIT": "observing"}


def events_for_analysis(result):
    if result.get("schema_version") != v26.SCHEMA_VERSION:
        raise ValueError("Unexpected V26 schema")
    agents = result.get("agents", [])
    if len(agents) != len(v26.AGENTS) or {a.get("agent") for a in agents} != set(v26.AGENTS):
        raise ValueError("Missing or duplicated agents")
    if result.get("orders_enabled") is not False or result.get("live_trading_approved") is not False:
        raise ValueError("Unsafe execution flag")
    observed_at = result["last_closed_candle_utc"]
    events = []
    for item in agents:
        decision = item["decision"]
        if decision not in v26.DECISIONS:
            raise ValueError("Unknown decision")
        events.append({
            "event_type": "agent.analysis",
            "agent_id": item["agent"],
            "state": STATUSES[decision],
            "decision": decision,
            "reason": item["reason"],
            "confidence": item["confidence"],
            "observed_candle_utc": observed_at,
        })
    commander = result.get("commander", {})
    if commander.get("decision") not in v26.DECISIONS:
        raise ValueError("Unknown commander decision")
    events.append({
        "event_type": "commander.consensus",
        "agent_id": "COMMANDER",
        "state": STATUSES[commander["decision"]],
        "decision": commander["decision"],
        "reason": commander["reason"],
        "risk_veto": commander["risk_veto"],
        "long_votes": commander["long_votes"],
        "short_votes": commander["short_votes"],
        "observed_candle_utc": observed_at,
    })
    return {
        "event_schema_version": VERSION,
        "symbol": result["symbol"],
        "timeframe": result["timeframe"],
        "observed_candle_utc": observed_at,
        "events": events,
        "paper_only": True,
        "orders_enabled": False,
        "independent_oos_verified": False,
        "live_trading_approved": False,
    }


def analyze_and_emit(candles):
    return events_for_analysis(v26.analyze(candles))


if __name__ == "__main__":
    import csv
    from pathlib import Path
    path = Path("data/history/BTC_5m.csv")
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    candles = [
        {"timestamp": int(r["timestamp"]), **{k: float(r[k]) for k in
         ("open", "high", "low", "close", "volume")}}
        for r in rows[-120:]
    ]
    print(json.dumps(analyze_and_emit(candles), ensure_ascii=False, indent=2))
