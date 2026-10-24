"""V108: attribute hypothetical closed trades to their entry-time regime.

No future data in signals or regime labels. Descriptive research only.
"""
import argparse
import csv
import json
import tempfile
from pathlib import Path

from chronological_holdout_v102 import split_csv
from ema_holdout_pipeline_v104 import _ema, INITIAL_CASH, FRACTION
from market_regime_v107 import classify
from multi_strategy_holdout_v105 import STRATEGIES
from cost_sensitivity_v106 import SCENARIOS

REGIMES = ("UPTREND", "DOWNTREND", "SIDEWAYS", "HIGH_VOLATILITY")
MIN_TRADES = 30

def attribute(rows, strategy, costs):
    if strategy not in STRATEGIES:
        raise ValueError("UNKNOWN_STRATEGY")
    if len(rows) < 80:
        raise ValueError("INSUFFICIENT_BARS")
    labels = {x["index"]: x["regime"] for x in classify(rows)}
    opens = [float(r["open"]) for r in rows]
    closes = [float(r["close"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    volumes = [float(r["volume"]) for r in rows]
    fast, slow = _ema(closes, 20), _ema(closes, 50)
    fee = costs["fee_bps"]/10000
    adverse = (costs["spread_bps"]/2+costs["slippage_bps"])/10000
    funding = costs["funding_bps_per_bar"]/10000
    cash, units, cost, fees, entry_regime = INITIAL_CASH, 0.0, 0.0, 0.0, None
    trades = []
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
            proceeds = units*opens[i]*(1-adverse)
            exit_fee = proceeds*fee
            cash += proceeds-exit_fee
            trades.append({"entry_regime": entry_regime,
                           "net_pnl": proceeds-exit_fee-cost-fees})
            units = 0.0
            entry_regime = None
        elif not units and buy:
            budget = cash*FRACTION
            fees = budget*fee/(1+fee)
            cost = budget-fees
            units = cost/(opens[i]*(1+adverse))
            cash -= budget
            # Label available when decision was made at close of bar k.
            entry_regime = labels[k]
        if units and funding:
            drag = units*closes[i]*funding
            cash -= drag
            fees += drag
    if units:
        proceeds = units*closes[-1]*(1-adverse)
        exit_fee = proceeds*fee
        cash += proceeds-exit_fee
        trades.append({"entry_regime": entry_regime,
                       "net_pnl": proceeds-exit_fee-cost-fees})
    summary = {}
    for regime in REGIMES:
        values = [t["net_pnl"] for t in trades if t["entry_regime"] == regime]
        wins = sum(v > 0 for v in values)
        summary[regime] = {
            "closed_trades": len(values),
            "net_pnl": round(sum(values), 6),
            "win_rate_pct": round(100*wins/len(values), 6) if values else None,
            "sample_sufficient": len(values) >= MIN_TRADES,
        }
    return {"closed_trades": len(trades), "by_entry_regime": summary,
            "attribution_total_net_pnl": round(sum(t["net_pnl"] for t in trades), 6),
            "attribution_method": "entry-time completed-bar regime; closed trades only",
            "research_only": True}

def run(source):
    with tempfile.TemporaryDirectory(prefix="spacebar-v108-") as tmp:
        train_path, valid_path = Path(tmp)/"train.csv", Path(tmp)/"validation.csv"
        split = split_csv(source, train_path, valid_path, ratio=0.7, min_rows=80)
        with train_path.open(newline="", encoding="utf-8") as f:
            train = list(csv.DictReader(f))
        with valid_path.open(newline="", encoding="utf-8") as f:
            valid = list(csv.DictReader(f))
        results = []
        for strategy in STRATEGIES:
            results.append({
                "strategy": strategy, "cost_scenario": "moderate",
                "train": attribute(train, strategy, SCENARIOS["moderate"]),
                "validation": attribute(valid, strategy, SCENARIOS["moderate"]),
            })
    return {"version": "V108.0", "status": "DESCRIPTIVE_REGIME_ATTRIBUTION",
            "split": split, "results": results,
            "minimum_trades_per_regime": MIN_TRADES,
            "research_only": True, "orders_enabled": False,
            "live_trading_approved": False, "validated_edge": False,
            "limitations": "Regimes are heuristics; small samples are not reliable. No strategy switching, causal effect or independent profitability validation."}

def main():
    parser = argparse.ArgumentParser(description="V108 regime-attributed hypothetical trade outcomes")
    parser.add_argument("history_csv")
    args = parser.parse_args()
    print(json.dumps(run(args.history_csv), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
