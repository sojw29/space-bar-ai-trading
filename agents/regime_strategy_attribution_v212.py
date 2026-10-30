"""V212 ex-post descriptive strategy results by completed validation windows.

Regime is known only AFTER each window; never use for entry decisions.
"""
import csv
import math
import tempfile
from pathlib import Path
from chronological_holdout_v102 import split_csv
from multi_strategy_holdout_v105 import MIN_BARS, STRATEGIES, _metrics

WINDOW = 90
THRESHOLD_PCT = 2.0


def assess_regime_strategy_performance(history_csv):
    with tempfile.TemporaryDirectory(prefix="spacebar-v212-") as folder:
        train, valid = Path(folder)/"train.csv", Path(folder)/"validation.csv"
        split_csv(history_csv, train, valid, ratio=0.7, min_rows=MIN_BARS)
        with valid.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
    if len(rows) < WINDOW:
        return {"version":"V212.0","status":"INSUFFICIENT_HOLDOUT_CANDLES",
                "window_candles":WINDOW,"windows":[],"summary":[],
                "research_only":True,"orders_allowed":False,
                "strategy_selection_enabled":False,"live_trading_approved":False}
    windows = []
    summary = {s:{r:[] for r in ("UP","DOWN","SIDEWAYS")} for s in STRATEGIES}
    for end in range(WINDOW, len(rows)+1, WINDOW):
        start = end-WINDOW
        segment = rows[start:end]
        initial, last = float(segment[0]["close"]), float(segment[-1]["close"])
        if not math.isfinite(initial) or not math.isfinite(last) or initial <= 0 or last <= 0:
            raise ValueError("INVALID_REGIME_PRICES")
        change = (last/initial-1)*100
        regime = "UP" if change > THRESHOLD_PCT else "DOWN" if change < -THRESHOLD_PCT else "SIDEWAYS"
        metrics = {}
        for strategy in STRATEGIES:
            m = _metrics(segment,strategy)
            metrics[strategy] = {
                "trades":m["trades"],"net_return_pct":m["return"],
                "max_drawdown_pct":m["max_drawdown"]}
            summary[strategy][regime].append(m)
        windows.append({
            "start_validation_index":start,"end_validation_index_exclusive":end,
            "candles":WINDOW,"regime":regime,
            "price_change_pct":round(change,6),"strategies":metrics})
    grouped = []
    for strategy in STRATEGIES:
        for regime in ("UP","DOWN","SIDEWAYS"):
            group = summary[strategy][regime]
            grouped.append({
                "strategy":strategy,"regime":regime,"windows":len(group),
                "mean_window_return_pct":round(sum(m["return"] for m in group)/len(group),6) if group else None,
                "positive_windows":sum(m["return"]>0 for m in group),
                "total_trades":sum(m["trades"] for m in group),
                "status":"DESCRIPTIVE_ONLY" if group else "NO_OBSERVATIONS"})
    return {"version":"V212.0","status":"DESCRIPTIVE_ONLY",
            "method":"EX_POST_NON_OVERLAPPING_WINDOW_STRATEGY_METRICS",
            "window_candles":WINDOW,"threshold_pct":THRESHOLD_PCT,
            "windows":windows,"summary":grouped,
            "unclassified_tail_candles":len(rows)%WINDOW,
            "research_only":True,"orders_allowed":False,
            "ranking_enabled":False,"strategy_selection_enabled":False,
            "live_trading_approved":False,
            "limitations":[
                "Regime labels use each completed window's final close (lookahead if used for trading).",
                "Strategy metrics are recomputed independently per window with fresh indicator warmup.",
                "Mean returns are arithmetic descriptive averages, not compounded performance.",
                "Sparse windows are not statistical evidence of a regime-dependent edge.",
                "No real-time trading, selection or execution permission."]}
