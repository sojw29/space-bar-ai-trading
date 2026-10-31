"""V234 offline auditable agent handoff; deterministic, not a model or trading engine."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from agent_research_runtime_v233 import SYMBOLS, RELATIONS, utc_time

def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")

def compile_handoff(payload, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("NAIVE_NOW")
    now = now.astimezone(timezone.utc)
    if not isinstance(payload, dict) or payload.get("version") != "V233.0" or payload.get("engine") != "OFFLINE_DETERMINISTIC_AGENT_CONTRACT":
        raise ValueError("INVALID_RUNTIME")
    for key, expected in (("research_only", True), ("orders_enabled", False),
                          ("realtime", False), ("ai_agents_running", False),
                          ("model_inference_performed", False),
                          ("trade_signals_available", False), ("backtest_verified", False)):
        if payload.get(key) is not expected:
            raise ValueError("UNSAFE_RUNTIME")
    source_time = utc_time(payload.get("source_generated_at_utc"))
    report_time = utc_time(payload.get("source_report_generated_at_utc"))
    runtime_time = utc_time(payload.get("generated_at_utc"))
    if not (source_time <= report_time <= runtime_time <= now):
        raise ValueError("INVALID_PROVENANCE")
    if not 0 <= (now - source_time).total_seconds() <= 8 * 3600:
        raise ValueError("STALE_SOURCE")
    markets = payload.get("markets")
    if not isinstance(markets, list) or len(markets) != 3:
        raise ValueError("INVALID_MARKETS")
    events = []
    for symbol in SYMBOLS:
        matches = [m for m in markets if isinstance(m, dict) and m.get("symbol") == symbol]
        if len(matches) != 1:
            raise ValueError("DUPLICATE_SYMBOL")
        market = matches[0]
        atlas, quant, guardian, commander = (market.get(name) for name in
                                              ("ATLAS", "QUANT", "GUARDIAN", "COMMANDER"))
        if not all(isinstance(x, dict) for x in (atlas, quant, guardian, commander)):
            raise ValueError("MISSING_AGENT")
        relation = atlas.get("sma_relationship")
        ratio = quant.get("volume_ratio_20")
        if atlas.get("status") != "DETERMINISTIC_OBSERVATION" or relation not in RELATIONS:
            raise ValueError("INVALID_ATLAS")
        import math
        if quant.get("status") != "DESCRIPTIVE_ONLY_NO_BACKTEST" or (ratio is not None and
            (type(ratio) not in (int, float) or not math.isfinite(ratio) or not 0 <= ratio < 1e12)):
            raise ValueError("INVALID_QUANT")
        if guardian.get("status") != "NO_TRADE_AUTHORIZATION" or guardian.get("orders_enabled") is not False:
            raise ValueError("INVALID_GUARDIAN")
        if commander.get("status") != "COMPILED_NOT_AI" or commander.get("recommendation", "INVALID") is not None:
            raise ValueError("INVALID_COMMANDER")
        for agent, observation in (
            ("ATLAS", {"sma_relationship": relation}),
            ("QUANT", {"volume_ratio_20": ratio}),
            ("GUARDIAN", {"orders_enabled": False, "authorization": "DENIED"}),
            ("COMMANDER", {"review": "DESCRIPTIVE_ONLY", "recommendation": None})
        ):
            events.append({"symbol": symbol, "agent": agent, "observation": observation,
                           "source_generated_at_utc": source_time.isoformat()})
    digest = hashlib.sha256(canonical({"source": payload, "events": events})).hexdigest()
    return {"version": "V234.0", "process": "DETERMINISTIC_AGENT_HANDOFF_AUDIT",
            "generated_at_utc": now.isoformat(), "source_generated_at_utc": source_time.isoformat(),
            "research_only": True, "orders_enabled": False, "ai_agents_running": False,
            "model_inference_performed": False, "trade_signals_available": False,
            "backtest_verified": False, "event_count": len(events), "events": events,
            "input_event_sha256": digest, "integrity_note": "SHA256 detects accidental changes, not authenticated signatures"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    source_path = Path(args.source)
    target = Path(args.destination)
    if source_path.resolve() == target.resolve():
        raise ValueError("SOURCE_DESTINATION_COLLISION")
    try:
        source = json.loads(source_path.read_text(encoding="utf-8"))
        output = compile_handoff(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    except (ValueError, OSError, TypeError, KeyError):
        target.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    main()
