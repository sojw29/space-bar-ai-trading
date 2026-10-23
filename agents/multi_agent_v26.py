"""SPACE BAR V26: deterministic multi-agent research engine (paper-only).

No LLM calls, network access, credentials, broker integration or live orders.
Signals are illustrative research heuristics, NOT validated trading strategies.
Only completed OHLCV candles may be passed to analyze().
"""
import json
import math
from datetime import datetime, timezone

AGENTS = ("ATLAS", "ORBIT", "ECHO", "PULSE", "QUANT", "APEX")
DECISIONS = ("LONG", "SHORT", "WAIT")
SCHEMA_VERSION = "26.0"


def _safe_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid " + label)
    return float(value)


def validate(candles, timeframe_seconds=300):
    if len(candles) < 55:
        raise ValueError("At least 55 completed candles required")
    previous = None
    for candle in candles:
        ts = candle.get("timestamp")
        if isinstance(ts, bool) or not isinstance(ts, int):
            raise ValueError("timestamp must be integer epoch seconds")
        if previous is not None and ts - previous != timeframe_seconds:
            raise ValueError("Candles must be contiguous and chronological")
        previous = ts
        o, h, l, c, v = (_safe_number(candle[k], k) for k in
                          ("open", "high", "low", "close", "volume"))
        if min(o, h, l, c) <= 0 or h < max(o, c) or l > min(o, c) or v < 0:
            raise ValueError("Invalid OHLCV candle")
    if candles[-1]["timestamp"] + timeframe_seconds > int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("Last candle has not completed")


def _vote(name, decision, reason, confidence=0.0):
    return {"agent": name, "decision": decision, "reason": reason,
            "confidence": round(float(confidence), 3)}


def analyze(candles):
    validate(candles)
    closes = [float(x["close"]) for x in candles]
    volumes = [float(x["volume"]) for x in candles]
    highs = [float(x["high"]) for x in candles]
    lows = [float(x["low"]) for x in candles]
    last = closes[-1]
    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-50:]) / 50
    vol_avg = sum(volumes[-21:-1]) / 20
    returns = [(closes[i] / closes[i - 1] - 1) for i in range(len(closes) - 20, len(closes))]
    volatility = math.sqrt(sum(x*x for x in returns) / len(returns))
    votes = []
    if last > sma20 > sma50:
        votes.append(_vote("ATLAS", "LONG", "Price > SMA20 > SMA50", 0.55))
    elif last < sma20 < sma50:
        votes.append(_vote("ATLAS", "SHORT", "Price < SMA20 < SMA50", 0.55))
    else:
        votes.append(_vote("ATLAS", "WAIT", "Moving averages not aligned"))
    bullish = closes[-1] > float(candles[-1]["open"])
    bearish = closes[-1] < float(candles[-1]["open"])
    strong_volume = vol_avg > 0 and volumes[-1] >= 1.3 * vol_avg
    votes.append(_vote("ORBIT", "LONG" if bullish else "SHORT" if bearish else "WAIT",
                       "Volume expansion with candle direction", 0.45)
                 if strong_volume and (bullish or bearish)
                 else _vote("ORBIT", "WAIT", "No volume expansion confirmation"))
    high20, low20 = max(highs[-21:-1]), min(lows[-21:-1])
    votes.append(_vote("ECHO", "LONG", "Closed above previous 20-bar high", 0.5)
                 if last > high20 else
                 _vote("ECHO", "SHORT", "Closed below previous 20-bar low", 0.5)
                 if last < low20 else _vote("ECHO", "WAIT", "Inside previous 20-bar range"))
    momentum = last / closes[-6] - 1
    votes.append(_vote("PULSE", "LONG" if momentum > 0.003 else "SHORT",
                       "Five-bar momentum threshold", 0.4)
                 if abs(momentum) > 0.003 else
                 _vote("PULSE", "WAIT", "Five-bar momentum below threshold"))
    votes.append(_vote("QUANT", "WAIT",
                       "No independently validated statistical model; abstaining"))
    # Conservative volatility gate; not a position sizing model.
    risk_block = volatility > 0.02
    votes.append(_vote("APEX", "WAIT", "Volatility exceeds paper risk gate"
                       if risk_block else "No risk veto; not a trade approval"))
    longs = sum(x["decision"] == "LONG" for x in votes)
    shorts = sum(x["decision"] == "SHORT" for x in votes)
    # Commander is deterministic: require >=3 aligned signals and no risk veto.
    decision = ("WAIT" if risk_block else "LONG" if longs >= 3 and shorts == 0
                else "SHORT" if shorts >= 3 and longs == 0 else "WAIT")
    return {
        "schema_version": SCHEMA_VERSION,
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "last_closed_candle_utc": datetime.fromtimestamp(
            candles[-1]["timestamp"], timezone.utc).isoformat(),
        "agents": votes,
        "commander": {"decision": decision, "long_votes": longs,
                      "short_votes": shorts, "risk_veto": risk_block,
                      "reason": "Deterministic consensus; no execution"},
        "metrics": {"sma20": round(sma20, 8), "sma50": round(sma50, 8),
                    "volume_ratio": round(volumes[-1] / vol_avg, 4) if vol_avg else None,
                    "realized_volatility": round(volatility, 6)},
        "paper_only": True,
        "orders_enabled": False,
        "independent_oos_verified": False,
        "live_trading_approved": False,
    }


if __name__ == "__main__":
    import csv
    from pathlib import Path
    path = Path("data/history/BTC_5m.csv")
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    data = [{**{k: float(row[k]) for k in ("open", "high", "low", "close", "volume")},
             "timestamp": int(row["timestamp"])} for row in rows[-120:]]
    print(json.dumps(analyze(data), indent=2))
