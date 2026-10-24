"""V103 compare separately supplied training/validation backtest summaries.

This is a reporting-only tool: it does not run strategies or establish
independent out-of-sample validity. No exchange orders or live trading.
"""
import argparse
import json
import math
from pathlib import Path

FIELDS = ("trades", "win_rate", "return", "profit_factor", "max_drawdown")
MAX_BYTES = 65536

def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)

def _validate(part, label):
    if not isinstance(part, dict) or set(part) != set(FIELDS):
        raise ValueError("INVALID_" + label + "_SCHEMA")
    trades = part["trades"]
    if type(trades) is not int or trades < 0 or trades > 1_000_000:
        raise ValueError("INVALID_TRADE_COUNT")
    for key in FIELDS[1:]:
        if not _finite(part[key]):
            raise ValueError("NONFINITE_METRIC")
    if not (0 <= part["win_rate"] <= 100 and 0 <= part["max_drawdown"] <= 100
            and part["return"] >= -100 and part["profit_factor"] >= 0):
        raise ValueError("INVALID_METRIC_RANGE")
    if trades == 0 and (part["win_rate"] != 0 or part["profit_factor"] != 0):
        raise ValueError("INCONSISTENT_ZERO_TRADES")

def compare(payload, min_trades=30):
    if type(min_trades) is not int or min_trades < 30:
        raise ValueError("INVALID_MIN_TRADES")
    if not isinstance(payload, dict) or set(payload) != {
        "strategy", "symbol", "timeframe", "train", "validation", "chronological",
        "independent_holdout", "strategy_frozen_before_validation"
    }:
        raise ValueError("INVALID_COMPARISON_SCHEMA")
    for key in ("strategy", "symbol", "timeframe"):
        value = payload[key]
        if not isinstance(value, str) or not 1 <= len(value) <= 64:
            raise ValueError("INVALID_IDENTITY")
    if (payload["chronological"] is not True or
            type(payload["independent_holdout"]) is not bool or
            type(payload["strategy_frozen_before_validation"]) is not bool):
        raise ValueError("INVALID_SPLIT_ATTESTATION")
    train = payload["train"]
    validation = payload["validation"]
    _validate(train, "TRAIN")
    _validate(validation, "VALIDATION")
    delta_return = round(validation["return"] - train["return"], 6)
    delta_win_rate = round(validation["win_rate"] - train["win_rate"], 6)
    delta_drawdown = round(validation["max_drawdown"] - train["max_drawdown"], 6)
    sample_ok = train["trades"] >= min_trades and validation["trades"] >= min_trades
    provenance_ok = payload["independent_holdout"] and payload["strategy_frozen_before_validation"]
    checks = [
        {"code": "TRADE_SAMPLE", "status": "PASS" if sample_ok else "BLOCKED"},
        {"code": "HOLDOUT_ATTESTATION", "status": "PASS" if provenance_ok else "BLOCKED"},
        {"code": "POSITIVE_VALIDATION_RETURN", "status": "PASS" if validation["return"] > 0 else "BLOCKED"},
        {"code": "POSITIVE_VALIDATION_PROFIT_FACTOR", "status": "PASS" if validation["profit_factor"] > 1 else "BLOCKED"},
    ]
    # Metrics can flag suspected degradation but cannot prove causal overfitting.
    degraded = (validation["return"] < train["return"] and
                validation["profit_factor"] < train["profit_factor"])
    return {
        "version": "V103.0", "strategy": payload["strategy"],
        "symbol": payload["symbol"], "timeframe": payload["timeframe"],
        "status": "REVIEW_REQUIRED",
        "train": train, "validation": validation,
        "delta_validation_minus_train": {
            "return_pct_points": delta_return,
            "win_rate_pct_points": delta_win_rate,
            "max_drawdown_pct_points": delta_drawdown,
        },
        "possible_generalization_degradation": degraded,
        "checks": checks, "minimum_trades_per_period": min_trades,
        "sample_sufficient": sample_ok,
        "holdout_attested": provenance_ok,
        "independently_verified": False,
        "research_only": True, "live_trading_approved": False,
        "strategy_profitable_verified": False,
        "note": "Reported metrics only. Provenance attestation is not independently verified; overfitting is not proven or ruled out."
    }

def main():
    parser = argparse.ArgumentParser(description="V103 offline train/validation backtest comparison")
    parser.add_argument("input_json", type=Path)
    args = parser.parse_args()
    if not args.input_json.is_file() or args.input_json.stat().st_size > MAX_BYTES:
        raise ValueError("MISSING_OR_OVERSIZED_INPUT")
    with args.input_json.open(encoding="utf-8") as file:
        payload = json.load(file)
    print(json.dumps(compare(payload), indent=2))
    return 1  # Never a live-trading approval gate

if __name__ == "__main__":
    raise SystemExit(main())
