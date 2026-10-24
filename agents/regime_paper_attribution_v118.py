"""V118 causal entry-regime attribution for hypothetical multi-strategy fills.

No strategy selection, independent holdout or live execution.
"""
import argparse
import json
from collections import defaultdict

from ema_signal_pipeline_v116 import read_history
from market_regime_v107 import classify
from multi_strategy_paper_v117 import STRATEGIES, generate
from offline_signal_replay_v115 import replay

REGIMES = ("UPTREND","DOWNTREND","SIDEWAYS","HIGH_VOLATILITY","UNCLASSIFIED")

def analyze(rows, budget_fraction=0.05):
    if not isinstance(rows,list) or len(rows)<202:
        raise ValueError("INSUFFICIENT_STRATEGY_HISTORY")
    labels = {x["index"]:x["regime"] for x in classify(rows)}
    results=[]
    for strategy in STRATEGIES:
        signals=generate(rows,strategy)
        paper=replay(signals,budget_fraction)
        fills=paper["hypothetical_fills"]
        # Every BUY starts a long-only trade, SELL closes it. Unclosed entries
        # remain explicitly unrealized and are not counted as completed trades.
        grouped={regime:{"entries":0,"closed_trades":0,
                         "gross_price_pnl":0.0} for regime in REGIMES}
        open_entry=None
        for fill in fills:
            if fill["side"]=="BUY":
                index=fill["signal_bar_index"]
                regime=labels.get(index,"UNCLASSIFIED")
                grouped[regime]["entries"]+=1
                open_entry={"regime":regime,"price":float(rows[fill["fill_bar_index"]]["open"])}
            elif fill["side"]=="SELL" and open_entry is not None:
                exit_price=float(rows[fill["fill_bar_index"]]["open"])
                bucket=grouped[open_entry["regime"]]
                bucket["closed_trades"]+=1
                bucket["gross_price_pnl"]+=exit_price/open_entry["price"]-1
                open_entry=None
        results.append({
            "strategy":strategy,
            "by_entry_regime":[{
                "regime":regime,"entries":grouped[regime]["entries"],
                "closed_trades":grouped[regime]["closed_trades"],
                "sum_gross_trade_return_pct":round(grouped[regime]["gross_price_pnl"]*100,8),
                "sample_sufficient":grouped[regime]["closed_trades"]>=30,
            } for regime in REGIMES],
            "open_position_at_end":open_entry is not None,
            "paper_total_return_pct":paper["performance"]["total_return_pct"],
            "paper_max_drawdown_pct":paper["performance"]["max_drawdown_pct"],
            "hypothetical_fills":len(fills),
        })
    return {"version":"V118.0","status":"DESCRIPTIVE_ENTRY_REGIME_ATTRIBUTION",
            "bars_processed":len(rows),"strategies":results,
            "regime_label_timing":"SIGNAL_BAR_CLOSE_BEFORE_NEXT_OPEN_FILL",
            "selection_or_approval":False,"research_only":True,
            "simulation_only":True,"exchange_connected":False,
            "orders_submitted_to_exchange":0,"live_trading_approved":False,
            "limitations":"Regime bucket return is an unweighted sum of gross per-trade price returns, NOT net PnL or a strategy equity curve; entry regime only. Paper totals include simulated fees. No independent holdout, spread, slippage or real fills."}

def run(path,budget_fraction=0.05):
    return analyze(read_history(path),budget_fraction)

def main():
    parser=argparse.ArgumentParser(description="V118 offline paper entry regime attribution")
    parser.add_argument("history_csv")
    parser.add_argument("--budget-fraction",type=float,default=0.05)
    args=parser.parse_args()
    print(json.dumps(run(args.history_csv,args.budget_fraction),indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
