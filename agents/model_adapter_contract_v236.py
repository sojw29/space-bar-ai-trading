"""V236 offline model-adapter boundary. No provider SDK, network, model invocation or trades."""
import argparse
from copy import deepcopy
import json
from datetime import datetime, timezone
from pathlib import Path
from agent_research_runtime_v233 import SYMBOLS, utc_time

AGENTS = ("ATLAS", "QUANT", "GUARDIAN", "COMMANDER")
MAX_PROMPT_CHARS = 800

def build_adapter_requests(payload, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("NAIVE_NOW")
    now = now.astimezone(timezone.utc)
    if not isinstance(payload, dict) or payload.get("version") != "V235.0" or payload.get("review_type") != "DETERMINISTIC_CROSS_SYMBOL_CONSISTENCY":
        raise ValueError("INVALID_SOURCE")
    for key, expected in (("research_only", True), ("orders_enabled", False),
                          ("ai_agents_running", False), ("model_inference_performed", False),
                          ("trade_signals_available", False)):
        if payload.get(key) is not expected:
            raise ValueError("UNSAFE_SOURCE")
    commander = payload.get("commander")
    if (not isinstance(commander, dict) or commander.get("status") != "DESCRIPTIVE_REVIEW_ONLY"
        or commander.get("trade_authorization") != "DENIED"
        or type(commander.get("trend_classifications_differ")) is not bool
        or type(commander.get("volume_data_availability_differs")) is not bool):
        raise ValueError("UNSAFE_COMMANDER")
    source_time = utc_time(payload.get("source_generated_at_utc"))
    report_time = utc_time(payload.get("generated_at_utc"))
    if not source_time <= report_time <= now or not 0 <= (now-source_time).total_seconds() <= 8*3600:
        raise ValueError("STALE_OR_FUTURE")
    markets = payload.get("markets")
    if not isinstance(markets, list) or len(markets) != 3:
        raise ValueError("INVALID_MARKETS")
    import math
    validated = []
    for symbol in SYMBOLS:
        matches = [m for m in markets if isinstance(m, dict) and m.get("symbol") == symbol]
        if len(matches) != 1:
            raise ValueError("DUPLICATE_MARKET")
        m = matches[0]
        if m.get("sma_relationship") not in ("SMA50_ABOVE_SMA200", "SMA50_BELOW_SMA200", "SMA_EQUAL"):
            raise ValueError("INVALID_TREND")
        ratio = m.get("volume_ratio_20")
        if ratio is not None and (type(ratio) not in (int, float) or not math.isfinite(ratio) or not 0 <= ratio < 1e12):
            raise ValueError("INVALID_VOLUME")
        if m.get("guardian") != "DENIED" or m.get("review_status") != "DESCRIPTIVE_ONLY":
            raise ValueError("UNSAFE_MARKET")
        validated.append({"symbol": symbol, "trend": m["sma_relationship"], "volume_ratio_20": ratio})
    requests = []
    for agent in AGENTS:
        facts = {"markets": deepcopy(validated), "trend_classifications_differ": commander["trend_classifications_differ"],
                 "volume_data_availability_differs": commander["volume_data_availability_differs"]}
        request = {"agent": agent, "mode": "OFFLINE_INPUT_ONLY",
                   "instruction": "Describe only the supplied observations. Do not recommend trades, forecast returns, claim model execution, or issue orders.",
                   "facts": facts, "trade_authorization": "DENIED"}
        if len(request["instruction"]) > MAX_PROMPT_CHARS:
            raise ValueError("PROMPT_TOO_LONG")
        requests.append(request)
    return {"version": "V236.0", "type": "UNEXECUTED_MODEL_ADAPTER_REQUESTS",
            "generated_at_utc": now.isoformat(), "source_generated_at_utc": source_time.isoformat(),
            "research_only": True, "orders_enabled": False, "model_inference_performed": False,
            "ai_agents_running": False, "trade_signals_available": False,
            "network_access_required": False, "requests": requests,
            "note": "Adapter inputs only; no model provider configured or called."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    target = Path(args.destination)
    try:
        data = json.loads(Path(args.source).read_text(encoding="utf-8"))
        result = build_adapter_requests(data)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    except (ValueError, TypeError, KeyError, OSError):
        target.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    main()
