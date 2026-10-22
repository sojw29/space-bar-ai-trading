"""V16: predeclared-candidate cost and fold stability audit.

Paper research only. ALL 2025-2026 historical data was previously inspected.
No independent OOS claims, no tuning/selection from diagnostic, no live orders.
V15 and V14 are intentionally left unchanged.
"""
import csv
import os

import tester_v10 as v10
import tester_v11 as v11
import tester_v14 as v14
import tester_v15 as v15
from tester import load_data, prepare, walk_forward_windows

REPORT_DIR = "reports/v16"
CANDIDATES = ("V15_BASELINE", "ATR_020_030", "LONG_ONLY", "ADX25_30_ATR015_025")
COSTS = (
    ("BASE", 0.00055, 0.00020),
    ("STRESS", 0.00100, 0.00050),
    ("SEVERE", 0.00150, 0.00100),
)


def save_csv(name, rows, fields):
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, name), "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def evaluate_one(candles, indicators, htf, windows, config, period, scenario, fee, slippage):
    results = []
    folds = []
    for window in windows:
        result = v10.simulate(
            candles, indicators, htf, config, window["valid_start"],
            window["valid_end"], fee, slippage, window["fold"], scenario,
        )
        results.append(result)
        metric = v15.calculate_metrics([result])
        folds.append({
            "period": period, "candidate": config["name"], "scenario": scenario,
            "fold": window["fold"], "trades": metric["trades"],
            "return_pct": metric["return_pct"], "profit_factor": metric["profit_factor"],
            "max_drawdown_pct": metric["max_drawdown_pct"],
        })
    return v15.calculate_metrics(results), folds


def run():
    v15.validate_configs()
    candles = load_data(v15.SYMBOL, v15.TIMEFRAME)
    v14.validate_history(candles)
    indicators = prepare(candles)
    htf = v10.build_htf_filter(candles)
    atr = v11.calculate_atr_pct(candles, period=14)
    split = int(len(candles) * v15.TRAIN_RATIO)
    train = walk_forward_windows(split)
    if len(train) != 4 or any(w["valid_end"] > split for w in train):
        raise RuntimeError("Invalid chronological training folds")
    # Retrospective diagnostic was previously inspected; NOT fresh OOS.
    diagnostic = [{"fold": "PREVIOUSLY_INSPECTED", "valid_start": split, "valid_end": len(candles)}]
    configs = {c["name"]: c for c in v15.CONFIGS}
    if any(name not in configs for name in CANDIDATES):
        raise RuntimeError("Missing predeclared candidate")
    original_signal, original_atr = v10.get_v10_signal, v15.ACTIVE_ATR
    v10.get_v10_signal, v15.ACTIVE_ATR = v15.v15_signal_adapter, atr
    summary, fold_rows = [], []
    try:
        for period, windows in (("TRAIN_REPLAY", train), ("INSPECTED_DIAGNOSTIC", diagnostic)):
            for name in CANDIDATES:
                for scenario, fee, slippage in COSTS:
                    metric, rows = evaluate_one(
                        candles, indicators, htf, windows, configs[name],
                        period, scenario, fee, slippage,
                    )
                    fold_rows.extend(rows)
                    summary.append({
                        "period": period, "candidate": name, "scenario": scenario,
                        "fee_per_side": fee, "slippage_per_side": slippage,
                        "trades": metric["trades"], "wins": metric["wins"],
                        "win_rate_pct": metric["win_rate_pct"],
                        "return_pct": metric["return_pct"],
                        "profit_factor": metric["profit_factor"],
                        "expectancy_usd": metric["expectancy_usd"],
                        "max_drawdown_pct": metric["max_drawdown_pct"],
                        "positive_folds": metric["positive_folds"],
                        "total_folds": metric["total_folds"],
                        "independent_oos": False,
                    })
                    print(period, name, scenario,
                          "trades", metric["trades"],
                          "return_pct", metric["return_pct"],
                          "PF", metric["profit_factor"], flush=True)
    finally:
        v10.get_v10_signal, v15.ACTIVE_ATR = original_signal, original_atr

    save_csv("summary.csv", summary, [
        "period", "candidate", "scenario", "fee_per_side", "slippage_per_side",
        "trades", "wins", "win_rate_pct", "return_pct", "profit_factor",
        "expectancy_usd", "max_drawdown_pct", "positive_folds", "total_folds",
        "independent_oos",
    ])
    save_csv("folds.csv", fold_rows, [
        "period", "candidate", "scenario", "fold", "trades", "return_pct",
        "profit_factor", "max_drawdown_pct",
    ])
    print("V16 COMPLETED — RETROSPECTIVE AUDIT ONLY; NO LIVE TRADING APPROVAL")


if __name__ == "__main__":
    run()
