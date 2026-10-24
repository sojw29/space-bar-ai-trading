"""V106 offline execution-cost sensitivity for fixed holdout strategies.

Models spread, slippage and per-side fees as deterministic adverse price
adjustments. Funding is a configurable per-bar notional drag, not an
exchange-specific settlement model. Research only; no real orders.
"""
import argparse
import csv
import json
import math
import tempfile
from pathlib import Path
from chronological_holdout_v102 import split_csv
from holdout_comparison_v103 import compare
from multi_strategy_holdout_v105 import STRATEGIES, MIN_BARS
from ema_holdout_pipeline_v104 import _ema, INITIAL_CASH, FRACTION

SCENARIOS = {
    "baseline": {"fee_bps": 5.5, "spread_bps": 0.0, "slippage_bps": 0.0, "funding_bps_per_bar": 0.0},
    "moderate": {"fee_bps": 5.5, "spread_bps": 2.0, "slippage_bps": 2.0, "funding_bps_per_bar": 0.0},
    "stress": {"fee_bps": 7.5, "spread_bps": 8.0, "slippage_bps": 8.0, "funding_bps_per_bar": 0.1},
}

def backtest(rows, strategy, costs):
    if strategy not in STRATEGIES:
        raise ValueError("UNKNOWN_STRATEGY")
    if len(rows) < MIN_BARS:
        raise ValueError("INSUFFICIENT_BARS")
    if not isinstance(costs, dict) or set(costs) != {
            "fee_bps", "spread_bps", "slippage_bps", "funding_bps_per_bar"}:
        raise ValueError("INVALID_COST_SCHEMA")
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 or v > 100
           for v in costs.values()):
        raise ValueError("INVALID_COST_RATE")
    fee = costs["fee_bps"] / 10000
    adverse = (costs["spread_bps"] / 2 + costs["slippage_bps"]) / 10000
    funding = costs["funding_bps_per_bar"] / 10000
    opens = [float(r["open"]) for r in rows]
    closes = [float(r["close"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    volumes = [float(r["volume"]) for r in rows]
    fast, slow = _ema(closes, 20), _ema(closes, 50)
    cash, units, cost, entry_fee = INITIAL_CASH, 0.0, 0.0, 0.0
    nets = []
    peak, drawdown = INITIAL_CASH, 0.0
    for i in range(52, len(rows)):
        k = i-1
        if strategy == "EMA_CROSS":
            buy = fast[k-1] <= slow[k-1] and fast[k] > slow[k]
            sell = fast[k-1] >= slow[k-1] and fast[k] < slow[k]
        elif strategy == "EMA_PULLBACK":
            buy = fast[k] > slow[k] and closes[k-1] <= fast[k-1] and closes[k] > fast[k]
            sell = closes[k] < slow[k]
        else:
            buy = (closes[k] > max(highs[k-20:k]) and
                   volumes[k] >= 1.5*sum(volumes[k-20:k])/20 and closes[k] > slow[k])
            sell = closes[k] < fast[k]
        if units and sell:
            proceeds = units * opens[i] * (1-adverse)
            exit_fee = proceeds * fee
            cash += proceeds - exit_fee
            nets.append(proceeds - exit_fee - cost - entry_fee)
            units = 0.0
        elif not units and buy:
            budget = cash * FRACTION
            entry_fee = budget * fee / (1+fee)
            cost = budget-entry_fee
            units = cost / (opens[i]*(1+adverse))
            cash -= budget
        if units and funding:
            drag = units * closes[i] * funding
            cash -= drag
            # Include ongoing funding in eventual closed-trade net PnL.
            entry_fee += drag
        equity = cash + units * closes[i]
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak-equity)/peak*100)
    if units:
        proceeds = units * closes[-1] * (1-adverse)
        exit_fee = proceeds * fee
        cash += proceeds - exit_fee
        nets.append(proceeds - exit_fee - cost - entry_fee)
        peak = max(peak, cash)
        drawdown = max(drawdown, (peak-cash)/peak*100)
    winners = [x for x in nets if x > 0]
    losers = [x for x in nets if x < 0]
    return {"trades": len(nets),
            "win_rate": round(100*len(winners)/len(nets), 6) if nets else 0.0,
            "return": round((cash/INITIAL_CASH-1)*100, 6),
            "profit_factor": round(sum(winners)/abs(sum(losers)), 6) if losers else 0.0,
            "max_drawdown": round(drawdown, 6)}

def run(source, symbol="BTC", timeframe="5m"):
    with tempfile.TemporaryDirectory(prefix="spacebar-v106-") as tmp:
        train_path = Path(tmp)/"train.csv"
        valid_path = Path(tmp)/"validation.csv"
        split = split_csv(source, train_path, valid_path, ratio=0.7, min_rows=MIN_BARS)
        with train_path.open(newline="", encoding="utf-8") as f:
            train = list(csv.DictReader(f))
        with valid_path.open(newline="", encoding="utf-8") as f:
            validation = list(csv.DictReader(f))
        results = []
        for strategy in STRATEGIES:
            for scenario, costs in SCENARIOS.items():
                report = compare({
                    "strategy": strategy, "symbol": symbol, "timeframe": timeframe,
                    "train": backtest(train, strategy, costs),
                    "validation": backtest(validation, strategy, costs),
                    "chronological": True, "independent_holdout": True,
                    "strategy_frozen_before_validation": True,
                })
                results.append({"scenario": scenario, "costs": costs, "comparison": report})
    return {"version": "V106.0", "status": "RESEARCH_REVIEW_REQUIRED",
            "split": split, "results": results,
            "strategy_count": len(STRATEGIES), "scenario_count": len(SCENARIOS),
            "research_only": True, "orders_enabled": False,
            "live_trading_approved": False, "validated_edge": False,
            "limitations": "Hypothetical fixed costs; funding approximated each bar; no exchange fills, latency, liquidation, or actual order book."}

def main():
    parser = argparse.ArgumentParser(description="V106 offline cost stress tests")
    parser.add_argument("history_csv")
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--timeframe", default="5m")
    args = parser.parse_args()
    print(json.dumps(run(args.history_csv, args.symbol, args.timeframe), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
