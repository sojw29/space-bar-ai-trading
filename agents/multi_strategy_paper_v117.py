"""V117 fixed multi-strategy offline signal-to-paper comparison.

All signals use completed OHLCV bars and V115 next-open hypothetical fills.
No live orders, exchange connection, parameter fitting or strategy approval.
"""
import argparse
import json
import math
from decimal import Decimal
from ema_signal_pipeline_v116 import read_history, generate as ema_cross_signals
from offline_signal_replay_v115 import replay

STRATEGIES = ("EMA_CROSS", "EMA_PULLBACK", "VOLUME_BREAKOUT")

def _ema(prev, close, period):
    return close if prev is None else prev + 2.0/(period+1)*(close-prev)

def generate(rows, strategy):
    if strategy not in STRATEGIES:
        raise ValueError("UNKNOWN_STRATEGY")
    if not isinstance(rows, list) or len(rows) < 202:
        raise ValueError("INSUFFICIENT_STRATEGY_HISTORY")
    if strategy == "EMA_CROSS":
        return ema_cross_signals(rows)
    enriched = []
    ema50 = ema200 = None
    volumes = []
    highs = []
    lows = []
    for i, row in enumerate(rows):
        close = float(row["close"])
        op = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        volume = float(row["volume"])
        previous_ema50 = ema50
        ema50 = _ema(ema50, close, 50)
        ema200 = _ema(ema200, close, 200)
        signal = "HOLD"
        # All lookback extrema/volume means are previous-bar only.
        if i >= 200:
            if strategy == "EMA_PULLBACK":
                if (ema50 > ema200 and previous_ema50 is not None and
                        low <= previous_ema50 and close > ema50 and close > op):
                    signal = "BUY"
                elif ema50 < ema200 and close < ema50:
                    signal = "SELL"
            elif strategy == "VOLUME_BREAKOUT":
                prior_high = max(highs[-20:])
                prior_low = min(lows[-20:])
                mean_vol = sum(volumes[-20:])/20
                if close > prior_high and close > ema200 and volume > mean_vol*1.5:
                    signal = "BUY"
                elif close < prior_low or close < ema200:
                    signal = "SELL"
        enriched.append({**row, "signal":signal})
        highs.append(high)
        lows.append(low)
        volumes.append(volume)
    return enriched

def compare(rows, budget_fraction=0.05):
    results = []
    for strategy in STRATEGIES:
        signals = generate(rows, strategy)
        report = replay(signals, budget_fraction)
        perf = report["performance"]
        results.append({
            "strategy":strategy,
            "buy_signals":sum(r["signal"]=="BUY" for r in signals),
            "sell_signals":sum(r["signal"]=="SELL" for r in signals),
            "hypothetical_fills":len(report["hypothetical_fills"]),
            "total_return_pct":perf["total_return_pct"],
            "max_drawdown_pct":perf["max_drawdown_pct"],
            "fees_paid":perf["fees_paid"],
            "final_equity":perf["final_equity"],
            "kill_switch_active":perf["kill_switch_active"],
        })
    return {"version":"V117.0","status":"DESCRIPTIVE_OFFLINE_COMPARISON",
            "strategies":results,"bars_processed":len(rows),
            "same_data_same_budget_fraction":True,
            "selection_or_approval":False,
            "research_only":True,"simulation_only":True,
            "exchange_connected":False,"orders_submitted_to_exchange":0,
            "live_trading_approved":False,
            "limitations":"All strategies evaluated on the same historical input; no independent holdout, transaction slippage/spread, real fills, or verified edge. EMA200 initialized from first close; early indicator estimates depend on warmup history."}

def run(path, budget_fraction=0.05):
    rows = read_history(path)
    if len(rows) < 202:
        raise ValueError("INSUFFICIENT_STRATEGY_HISTORY")
    return compare(rows, budget_fraction)

def main():
    parser = argparse.ArgumentParser(description="V117 offline multi-strategy paper comparison")
    parser.add_argument("history_csv")
    parser.add_argument("--budget-fraction", type=float, default=0.05)
    args = parser.parse_args()
    print(json.dumps(run(args.history_csv,args.budget_fraction),indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
