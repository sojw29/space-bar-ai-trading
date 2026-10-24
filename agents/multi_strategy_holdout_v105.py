"""V105 deterministic multi-strategy comparison on chronological OHLCV holdouts.

Fixed, long-only research strategies. Next-open hypothetical fills, 0.055%
fee each side. No optimization, live orders, or profitability claims.
"""
import argparse
import csv
import json
import math
import tempfile
from pathlib import Path
from chronological_holdout_v102 import split_csv
from holdout_comparison_v103 import compare
from ema_holdout_pipeline_v104 import _ema, FEE_RATE, INITIAL_CASH, FRACTION

STRATEGIES = ("EMA_CROSS", "EMA_PULLBACK", "VOLUME_BREAKOUT")
MIN_BARS = 80

def _metrics(rows, strategy):
    if strategy not in STRATEGIES:
        raise ValueError("UNKNOWN_STRATEGY")
    if len(rows) < MIN_BARS:
        raise ValueError("INSUFFICIENT_BARS")
    opens = [float(r["open"]) for r in rows]
    closes = [float(r["close"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    volumes = [float(r["volume"]) for r in rows]
    ema20, ema50 = _ema(closes, 20), _ema(closes, 50)
    cash, units, cost, entry_fee = INITIAL_CASH, 0.0, 0.0, 0.0
    pnl = []
    peak, drawdown = INITIAL_CASH, 0.0
    for i in range(52, len(rows)):
        k = i - 1  # Only completed bar k and earlier are used.
        if strategy == "EMA_CROSS":
            buy = ema20[k-1] <= ema50[k-1] and ema20[k] > ema50[k]
            sell = ema20[k-1] >= ema50[k-1] and ema20[k] < ema50[k]
        elif strategy == "EMA_PULLBACK":
            buy = (ema20[k] > ema50[k] and closes[k-1] <= ema20[k-1]
                   and closes[k] > ema20[k])
            sell = closes[k] < ema50[k]
        else:
            prior_high = max(highs[k-20:k])
            avg_volume = sum(volumes[k-20:k]) / 20
            buy = (closes[k] > prior_high and
                   volumes[k] >= 1.5 * avg_volume and closes[k] > ema50[k])
            sell = closes[k] < ema20[k]
        price = opens[i]
        if units and sell:
            proceeds = units * price
            exit_fee = proceeds * FEE_RATE
            cash += proceeds - exit_fee
            pnl.append(proceeds - exit_fee - cost - entry_fee)
            units = 0.0
        elif not units and buy:
            budget = cash * FRACTION
            entry_fee = budget * FEE_RATE / (1 + FEE_RATE)
            cost = budget - entry_fee
            units = cost / price
            cash -= budget
        equity = cash + units * closes[i]
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak * 100)
    if units:
        proceeds = units * closes[-1]
        exit_fee = proceeds * FEE_RATE
        cash += proceeds - exit_fee
        pnl.append(proceeds - exit_fee - cost - entry_fee)
        peak = max(peak, cash)
        drawdown = max(drawdown, (peak - cash) / peak * 100)
    winners = [x for x in pnl if x > 0]
    losers = [x for x in pnl if x < 0]
    # Profit factor without losses is undefined; zero is a conservative
    # placeholder, not a mathematically meaningful profit factor.
    pf = sum(winners) / abs(sum(losers)) if losers else 0.0
    return {"trades": len(pnl),
            "win_rate": round(100 * len(winners) / len(pnl), 6) if pnl else 0.0,
            "return": round((cash / INITIAL_CASH - 1) * 100, 6),
            "profit_factor": round(pf, 6),
            "max_drawdown": round(drawdown, 6)}

def run(source, symbol="BTC", timeframe="5m"):
    with tempfile.TemporaryDirectory(prefix="spacebar-v105-") as tmp:
        train_file = Path(tmp) / "train.csv"
        valid_file = Path(tmp) / "validation.csv"
        split = split_csv(source, train_file, valid_file, ratio=0.7, min_rows=MIN_BARS)
        with train_file.open(newline="", encoding="utf-8") as handle:
            train = list(csv.DictReader(handle))
        with valid_file.open(newline="", encoding="utf-8") as handle:
            validation = list(csv.DictReader(handle))
        results = []
        for strategy in STRATEGIES:
            report = compare({
                "strategy": strategy, "symbol": symbol, "timeframe": timeframe,
                "train": _metrics(train, strategy),
                "validation": _metrics(validation, strategy),
                "chronological": True, "independent_holdout": True,
                "strategy_frozen_before_validation": True,
            })
            results.append(report)
    return {"version": "V105.0", "status": "RESEARCH_REVIEW_REQUIRED",
            "split": split, "strategies": results,
            "strategy_count": len(results), "research_only": True,
            "orders_enabled": False, "live_trading_approved": False,
            "validated_edge": False,
            "limitations": [
                "Fixed long-only demonstration strategies, not optimized.",
                "No slippage, spread, funding, partial fills or intrabar stops.",
                "Separate indicator warmups and hypothetical next-open fills.",
                "Holdout attestation is not independently audited.",
                "No statistical confidence or repeated walk-forward validation.",
            ]}

def main():
    parser = argparse.ArgumentParser(description="V105 offline multi-strategy holdout comparison")
    parser.add_argument("history_csv")
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--timeframe", default="5m")
    args = parser.parse_args()
    print(json.dumps(run(args.history_csv, args.symbol, args.timeframe), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
