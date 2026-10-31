"""V233: offline, deterministic agent runtime contract. NO network, model calls or orders."""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
RELATIONS = ("SMA50_ABOVE_SMA200", "SMA50_BELOW_SMA200", "SMA_EQUAL")

def utc_time(value):
    if not isinstance(value, str):
        raise ValueError("INVALID_TIMESTAMP")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return parsed.astimezone(timezone.utc)

def build_research(payload, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("NAIVE_NOW")
    now = now.astimezone(timezone.utc)
    if not isinstance(payload, dict) or payload.get("version") != "V229.0":
        raise ValueError("UNTRUSTED_VERSION")
    if (payload.get("report_type") != "DETERMINISTIC_COMMANDER_RESEARCH_BRIEF"
        or payload.get("research_only") is not True
        or payload.get("orders_enabled") is not False
        or payload.get("realtime") is not False
        or payload.get("ai_agents_running") is not False
        or payload.get("trade_signals_available") is not False
        or payload.get("backtest_verified") is not False):
        raise ValueError("UNSAFE_SOURCE_FLAGS")
    commander = payload.get("commander")
    if not isinstance(commander, dict) or commander.get("status") != "COMPILED_NOT_AI":
        raise ValueError("UNVERIFIED_COMMANDER")
    source_time = utc_time(payload.get("source_generated_at_utc"))
    report_time = utc_time(payload.get("generated_at_utc"))
    if not 0 <= (now - source_time).total_seconds() <= 8 * 3600:
        raise ValueError("STALE_SOURCE")
    if not source_time <= report_time <= now:
        raise ValueError("INVALID_PROVENANCE")
    markets = payload.get("markets")
    if not isinstance(markets, list) or len(markets) != len(SYMBOLS):
        raise ValueError("INCOMPLETE_MARKETS")
    result = []
    for symbol in SYMBOLS:
        matches = [m for m in markets if isinstance(m, dict) and m.get("symbol") == symbol]
        if len(matches) != 1:
            raise ValueError("DUPLICATE_OR_MISSING_SYMBOL")
        market = matches[0]
        relation = market.get("trend_observation")
        ratio = market.get("volume_ratio_20")
        if relation not in RELATIONS:
            raise ValueError("INVALID_TREND")
        if ratio is not None and (type(ratio) not in (int, float) or
                                  not math.isfinite(ratio) or not 0 <= ratio < 1e12):
            raise ValueError("INVALID_VOLUME_RATIO")
        if (market.get("risk_status") != "NO_TRADE_AUTHORIZATION" or
            market.get("research_conclusion") != "DESCRIPTIVE_ONLY"):
            raise ValueError("UNSAFE_MARKET")
        result.append({
            "symbol": symbol,
            "ATLAS": {"status": "DETERMINISTIC_OBSERVATION", "sma_relationship": relation},
            "QUANT": {"status": "DESCRIPTIVE_ONLY_NO_BACKTEST", "volume_ratio_20": ratio},
            "GUARDIAN": {"status": "NO_TRADE_AUTHORIZATION", "orders_enabled": False},
            "COMMANDER": {"status": "COMPILED_NOT_AI", "recommendation": None}
        })
    return {
        "version": "V233.0", "engine": "OFFLINE_DETERMINISTIC_AGENT_CONTRACT",
        "generated_at_utc": now.isoformat(),
        "source_generated_at_utc": source_time.isoformat(),
        "source_report_generated_at_utc": report_time.isoformat(),
        "research_only": True, "orders_enabled": False, "realtime": False,
        "ai_agents_running": False, "model_inference_performed": False,
        "trade_signals_available": False, "backtest_verified": False,
        "markets": result
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    source_path = Path(args.source)
    destination = Path(args.destination)
    if source_path.resolve() == destination.resolve():
        raise ValueError("SOURCE_DESTINATION_COLLISION")
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        result = build_research(payload)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError):
        destination.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    main()
