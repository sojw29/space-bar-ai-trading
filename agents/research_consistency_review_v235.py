"""V235: deterministic cross-symbol research disagreement review; no model or trades."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from agent_research_runtime_v233 import SYMBOLS, RELATIONS, utc_time

def review(payload, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("NAIVE_NOW")
    now = now.astimezone(timezone.utc)
    if not isinstance(payload, dict) or payload.get("version") != "V234.0" or payload.get("process") != "DETERMINISTIC_AGENT_HANDOFF_AUDIT":
        raise ValueError("INVALID_SOURCE")
    for key, expected in (("research_only", True), ("orders_enabled", False),
                          ("ai_agents_running", False), ("model_inference_performed", False),
                          ("trade_signals_available", False), ("backtest_verified", False)):
        if payload.get(key) is not expected:
            raise ValueError("UNSAFE_FLAGS")
    ts = utc_time(payload.get("source_generated_at_utc"))
    generated = utc_time(payload.get("generated_at_utc"))
    if not ts <= generated <= now or not 0 <= (now-ts).total_seconds() <= 8*3600:
        raise ValueError("INVALID_PROVENANCE")
    events = payload.get("events")
    if not isinstance(events, list) or len(events) != 12 or payload.get("event_count") != 12:
        raise ValueError("INVALID_EVENT_COUNT")
    if not isinstance(payload.get("input_event_sha256"), str) or len(payload["input_event_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in payload["input_event_sha256"]):
        raise ValueError("INVALID_DIGEST_FORMAT")
    rows = []
    for symbol in SYMBOLS:
        grouped = {}
        for event in events:
            if not isinstance(event, dict) or event.get("symbol") != symbol:
                continue
            agent = event.get("agent")
            if agent in grouped or agent not in ("ATLAS", "QUANT", "GUARDIAN", "COMMANDER"):
                raise ValueError("DUPLICATE_AGENT")
            if utc_time(event.get("source_generated_at_utc")) != ts:
                raise ValueError("INVALID_EVENT_PROVENANCE")
            observation = event.get("observation")
            if not isinstance(observation, dict):
                raise ValueError("INVALID_OBSERVATION")
            grouped[agent] = observation
        if set(grouped) != {"ATLAS", "QUANT", "GUARDIAN", "COMMANDER"}:
            raise ValueError("MISSING_AGENT")
        relation = grouped["ATLAS"].get("sma_relationship")
        ratio = grouped["QUANT"].get("volume_ratio_20")
        import math
        if relation not in RELATIONS or (ratio is not None and (type(ratio) not in (int,float) or not math.isfinite(ratio) or not 0 <= ratio < 1e12)):
            raise ValueError("INVALID_INDICATORS")
        if grouped["GUARDIAN"] != {"orders_enabled": False, "authorization": "DENIED"} or grouped["COMMANDER"] != {"review": "DESCRIPTIVE_ONLY", "recommendation": None}:
            raise ValueError("UNSAFE_HANDOFF")
        rows.append({"symbol": symbol, "sma_relationship": relation, "volume_ratio_20": ratio,
                     "guardian": "DENIED", "review_status": "DESCRIPTIVE_ONLY"})
    if any(not isinstance(e, dict) or e.get("symbol") not in SYMBOLS for e in events):
        raise ValueError("UNKNOWN_SYMBOL")
    trends = {r["sma_relationship"] for r in rows}
    trend_disagreement = len(trends) > 1
    volume_availability_disagreement = len({r["volume_ratio_20"] is None for r in rows}) > 1
    return {
        "version": "V235.0", "review_type": "DETERMINISTIC_CROSS_SYMBOL_CONSISTENCY",
        "generated_at_utc": now.isoformat(), "source_generated_at_utc": ts.isoformat(),
        "source_input_event_sha256": payload["input_event_sha256"],
        "research_only": True, "orders_enabled": False, "ai_agents_running": False,
        "model_inference_performed": False, "trade_signals_available": False,
        "commander": {"status": "DESCRIPTIVE_REVIEW_ONLY",
                      "trend_classifications_differ": trend_disagreement,
                      "volume_data_availability_differs": volume_availability_disagreement,
                      "trade_authorization": "DENIED",
                      "note": "Cross-symbol differences are not conflicting agent opinions or trade signals."},
        "markets": rows
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    target = Path(args.destination)
    try:
        data = json.loads(Path(args.source).read_text(encoding="utf-8"))
        output = review(data)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(output, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    except (ValueError, TypeError, KeyError, OSError):
        target.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    main()
