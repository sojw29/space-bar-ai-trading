"""V104 offline EMA20/50 train/validation research pipeline.

Single fixed strategy, no optimization. Signals at closed bar i; orders
hypothetically fill at next bar open. No exchange access or real orders.
"""
import argparse
import csv
import json
import math
import tempfile
from pathlib import Path
from chronological_holdout_v102 import split_csv
from holdout_comparison_v103 import compare
from holdout_evidence_adapter_v193 import assess_legacy_holdout

FEE_RATE = 0.00055
INITIAL_CASH = 10000.0
FRACTION = 0.1

def _ema(values, period):
    result = []
    alpha = 2.0 / (period + 1)
    current = values[0]
    for value in values:
        current = alpha * value + (1-alpha) * current
        result.append(current)
    return result

def backtest(csv_path):
    with Path(csv_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 80:
        raise ValueError("INSUFFICIENT_BACKTEST_BARS")
    op = [float(r["open"]) for r in rows]
    cl = [float(r["close"]) for r in rows]
    fast, slow = _ema(cl, 20), _ema(cl, 50)
    cash = INITIAL_CASH
    units = 0.0
    entry_cost = 0.0
    entry_fee = 0.0
    closed = []
    peak = INITIAL_CASH
    max_dd = 0.0
    # On each i, act only on signals confirmed at i-1, fill at open i.
    for i in range(51, len(rows)):
        buy = fast[i-2] <= slow[i-2] and fast[i-1] > slow[i-1]
        sell = fast[i-2] >= slow[i-2] and fast[i-1] < slow[i-1]
        price = op[i]
        if units and sell:
            proceeds = units * price
            fee = proceeds * FEE_RATE
            cash += proceeds - fee
            closed.append(proceeds - fee - entry_cost - entry_fee)
            units = 0.0
        elif not units and buy:
            budget = cash * FRACTION
            fee = budget * FEE_RATE / (1 + FEE_RATE)
            entry_cost = budget - fee
            entry_fee = fee
            units = entry_cost / price
            cash -= budget
        equity = cash + units * cl[i]
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak-equity)/peak*100)
    if units:
        proceeds = units * cl[-1]
        fee = proceeds * FEE_RATE
        cash += proceeds - fee
        closed.append(proceeds - fee - entry_cost - entry_fee)
        peak = max(peak, cash)
        max_dd = max(max_dd, (peak-cash)/peak*100)
    wins = [x for x in closed if x > 0]
    losses = [x for x in closed if x < 0]
    # No losses => PF undefined; report 0 rather than invent infinity.
    pf = sum(wins)/abs(sum(losses)) if losses else 0.0
    return {
        "trades": len(closed),
        "win_rate": round(len(wins)/len(closed)*100, 6) if closed else 0.0,
        "return": round((cash/INITIAL_CASH-1)*100, 6),
        "profit_factor": round(pf, 6),
        "max_drawdown": round(max_dd, 6),
    }

def run(source, symbol="BTC", timeframe="5m", ratio=0.7):
    with tempfile.TemporaryDirectory(prefix="spacebar-v104-") as d:
        train_path = Path(d)/"train.csv"
        valid_path = Path(d)/"validation.csv"
        split = split_csv(source, train_path, valid_path, ratio=ratio, min_rows=80)
        train = backtest(train_path)
        validation = backtest(valid_path)
    result = compare({
        "strategy": "EMA20_50_LONG_ONLY_FIXED", "symbol": symbol,
        "timeframe": timeframe, "train": train, "validation": validation,
        "chronological": True,
        "independent_holdout": True,
        "strategy_frozen_before_validation": True,
    })
    output = {
        "version": "V104.0", "status": "RESEARCH_REVIEW_REQUIRED",
        "split": split, "comparison": result,
        "fee_rate_per_side": FEE_RATE,
        "strategy": "FIXED_EMA20_50_NEXT_OPEN_LONG_ONLY",
        "assumptions": "No slippage, spread, funding, partial fills or intrabar stops. Separate EMA warmups per split.",
        "research_only": True, "live_trading_approved": False,
        "orders_enabled": False, "oos_profitability_verified": False,
    }
    output["evidence_assessment"] = assess_legacy_holdout(output)
    return output

def main():
    parser = argparse.ArgumentParser(description="V104 fixed EMA offline holdout research")
    parser.add_argument("history_csv")
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--timeframe", default="5m")
    args = parser.parse_args()
    print(json.dumps(run(args.history_csv, args.symbol, args.timeframe), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
