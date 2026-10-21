# ============================================================
# SPACE BAR AI TRADING
# TESTER V12.0
# ATR REGIME + DIRECTION + OUT-OF-SAMPLE RESEARCH
# BTC 5M | BINANCE USDT FUTURES
# PAPER RESEARCH ONLY
# ============================================================

import csv
import os
from copy import deepcopy

import tester_v10 as v10
import tester_v11 as v11

from tester import (
    load_data,
    prepare,
    walk_forward_windows,
)

# ============================================================
# SETTINGS
# ============================================================

SYMBOL = "BTC"
TIMEFRAME = "5"

REPORT_DIR = "reports/v12"

TRAIN_RATIO = 0.80

MIN_TRADES = 30
MIN_POSITIVE_FOLDS = 3
MIN_PROFIT_FACTOR = 1.10

BASE_FEE = 0.00055
BASE_SLIPPAGE = 0.00020

STRESS_FEE = 0.00100
STRESS_SLIPPAGE = 0.00050

# ============================================================
# RESEARCH CONFIGURATIONS
# ============================================================

BASE_CONFIG = {
    "name": "HTF_ATR_LOW",
    "adx_min": 25,
    "volume_mult": 0.0,
    "htf_filter": True,
    "stop": 0.006,
    "target": 0.012,
    "atr_min": 0.15,
    "atr_max": 0.60,
    "side": "BOTH",
    "signal_mode": "CROSS",
}

CONFIGS = []


def add_config(name, **changes):

    config = deepcopy(BASE_CONFIG)

    config.update(changes)
    config["name"] = name

    CONFIGS.append(config)


# Original V11 candidate
add_config("V11_ATR_LOW")

# ATR ranges
add_config(
    "ATR_015_030",
    atr_min=0.15,
    atr_max=0.30,
)

add_config(
    "ATR_030_045",
    atr_min=0.30,
    atr_max=0.45,
)

add_config(
    "ATR_045_060",
    atr_min=0.45,
    atr_max=0.60,
)

add_config(
    "ATR_010_040",
    atr_min=0.10,
    atr_max=0.40,
)

add_config(
    "ATR_020_050",
    atr_min=0.20,
    atr_max=0.50,
)

# Direction
add_config(
    "ATR_LONG_ONLY",
    side="LONG",
)

add_config(
    "ATR_SHORT_ONLY",
    side="SHORT",
)

# ADX
add_config(
    "ATR_ADX20",
    adx_min=20,
)

add_config(
    "ATR_ADX30",
    adx_min=30,
)

add_config(
    "ATR_ADX35",
    adx_min=35,
)

# Volume
add_config(
    "ATR_VOLUME_110",
    volume_mult=1.10,
)

add_config(
    "ATR_VOLUME_120",
    volume_mult=1.20,
)

# Reward/risk
add_config(
    "ATR_RR_1_15",
    target=0.009,
)

add_config(
    "ATR_RR_1_25",
    target=0.015,
)

# Pullback
add_config(
    "ATR_PULLBACK",
    signal_mode="PULLBACK",
)

# ============================================================
# REPORT FIELDS
# ============================================================

RANKING_FIELDS = [
    "configuration",
    "trades",
    "wins",
    "losses",
    "win_rate_pct",
    "return_pct",
    "profit_factor",
    "stress_return_pct",
    "stress_profit_factor",
    "positive_folds",
    "total_folds",
    "expectancy_usd",
    "average_win_usd",
    "average_loss_usd",
    "payoff_ratio",
    "max_drawdown_pct",
    "eligible",
    "rejection_reasons",
]

HOLDOUT_FIELDS = [
    "configuration",
    "scenario",
    "trades",
    "wins",
    "losses",
    "win_rate_pct",
    "return_pct",
    "profit_factor",
    "expectancy_usd",
    "max_drawdown_pct",
]

FOLD_FIELDS = [
    "configuration",
    "scenario",
    "fold",
    "trades",
    "return_pct",
    "profit_factor",
    "max_drawdown_pct",
]

TRADE_FIELDS = v10.TRADE_FIELDS

# ============================================================
# HELPERS
# ============================================================

def save_csv(path, rows, fields):

    os.makedirs(
        os.path.dirname(path),
        exist_ok=True,
    )

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


def safe_round(value):

    if value is None:
        return None

    return round(value, 4)


def evaluate(
    candles,
    indicators,
    htf_directions,
    windows,
    config,
    scenario,
    fee,
    slippage,
):

    results = []
    fold_rows = []

    for window in windows:

        result = v10.simulate(
            candles,
            indicators,
            htf_directions,
            config,
            window["valid_start"],
            window["valid_end"],
            fee,
            slippage,
            window["fold"],
            scenario,
        )

        results.append(result)

        fold_metrics = v10.summarize(
            [result]
        )

        fold_rows.append({
            "configuration": config["name"],
            "scenario": scenario,
            "fold": window["fold"],
            "trades": fold_metrics["trades"],
            "return_pct": safe_round(
                result["return_pct"]
            ),
            "profit_factor": safe_round(
                fold_metrics["profit_factor"]
            ),
            "max_drawdown_pct": safe_round(
                result["max_drawdown_pct"]
            ),
        })

    metrics = v10.summarize(results)

    return metrics, fold_rows


def rejection_reasons(base, stress):

    reasons = []

    if base["trades"] < MIN_TRADES:
        reasons.append(
            "INSUFFICIENT_TRADES"
        )

    if (
        base["positive_folds"]
        < MIN_POSITIVE_FOLDS
    ):
        reasons.append(
            "INSUFFICIENT_POSITIVE_FOLDS"
        )

    if base["return_pct"] <= 0:
        reasons.append(
            "NEGATIVE_RETURN"
        )

    if (
        base["profit_factor"] is None
        or base["profit_factor"]
        < MIN_PROFIT_FACTOR
    ):
        reasons.append(
            "LOW_PROFIT_FACTOR"
        )

    if stress["return_pct"] <= 0:
        reasons.append(
            "STRESS_TEST_FAILED"
        )

    return reasons


def build_ranking_row(config, base, stress):

    reasons = rejection_reasons(
        base,
        stress,
    )

    return {
        "configuration": config["name"],
        "trades": base["trades"],
        "wins": base["wins"],
        "losses": base["losses"],
        "win_rate_pct": safe_round(
            base["win_rate_pct"]
        ),
        "return_pct": safe_round(
            base["return_pct"]
        ),
        "profit_factor": safe_round(
            base["profit_factor"]
        ),
        "stress_return_pct": safe_round(
            stress["return_pct"]
        ),
        "stress_profit_factor": safe_round(
            stress["profit_factor"]
        ),
        "positive_folds": base["positive_folds"],
        "total_folds": base["total_folds"],
        "expectancy_usd": safe_round(
            base["expectancy_usd"]
        ),
        "average_win_usd": safe_round(
            base["average_win_usd"]
        ),
        "average_loss_usd": safe_round(
            base["average_loss_usd"]
        ),
        "payoff_ratio": safe_round(
            base["payoff_ratio"]
        ),
        "max_drawdown_pct": safe_round(
            base["max_drawdown_pct"]
        ),
        "eligible": len(reasons) == 0,
        "rejection_reasons": (
            "|".join(reasons)
            if reasons
            else "PASS"
        ),
    }


# ============================================================
# MAIN
# ============================================================

def test_all():

    print("=" * 60)
    print("SPACE BAR AI - TESTER V12.0")
    print("ATR REGIME + OUT-OF-SAMPLE RESEARCH")
    print("=" * 60)

    candles = load_data(
        SYMBOL,
        TIMEFRAME,
    )

    v10.validate_data(candles)

    indicators = prepare(candles)

    htf_directions = v10.build_htf_filter(
        candles
    )

    atr_pct = v11.calculate_atr_pct(
        candles,
        period=14,
    )

    total = len(candles)

    split = int(
        total * TRAIN_RATIO
    )

    if split < 1000:
        raise RuntimeError(
            "Insufficient training data."
        )

    # Generate walk-forward windows only
    # inside the training portion.
    train_windows = walk_forward_windows(
        split
    )

    if not train_windows:
        raise RuntimeError(
            "No training windows available."
        )

    for window in train_windows:

        if window["valid_end"] > split:
            raise RuntimeError(
                "Training window overlaps holdout."
            )

    print(
        "Total candles:", total,
        flush=True,
    )

    print(
        "Training candles:", split,
        flush=True,
    )

    print(
        "Holdout candles:", total - split,
        flush=True,
    )

    print(
        "Training folds:",
        len(train_windows),
        flush=True,
    )

    ranking = []
    fold_report = []
    train_trades = []

    original_signal = v10.get_v10_signal
    original_atr = v11.ACTIVE_ATR

    # Use V11 signal generation
    # with the V10 execution simulator.
    v11.ACTIVE_ATR = atr_pct
    v10.get_v10_signal = v11.v11_signal_adapter

    try:

        # ====================================
        # TRAINING EVALUATION
        # ====================================

        for config in CONFIGS:

            base, base_folds = evaluate(
                candles,
                indicators,
                htf_directions,
                train_windows,
                config,
                "BASE",
                BASE_FEE,
                BASE_SLIPPAGE,
            )

            stress, stress_folds = evaluate(
                candles,
                indicators,
                htf_directions,
                train_windows,
                config,
                "STRESS",
                STRESS_FEE,
                STRESS_SLIPPAGE,
            )

            row = build_ranking_row(
                config,
                base,
                stress,
            )

            ranking.append(row)

            fold_report.extend(
                base_folds
            )

            fold_report.extend(
                stress_folds
            )

            train_trades.extend(
                base["trade_log"]
            )

            train_trades.extend(
                stress["trade_log"]
            )

            print(
                config["name"],
                "| Return:",
                row["return_pct"],
                "| Stress:",
                row["stress_return_pct"],
                "| PF:",
                row["profit_factor"],
                "| Eligible:",
                row["eligible"],
                flush=True,
            )

        # ====================================
        # TRAINING RANKING
        # ====================================

        ranking.sort(
            key=lambda row: (
                row["eligible"],
                row["stress_return_pct"],
                row["return_pct"],
                row["profit_factor"] or 0,
            ),
            reverse=True,
        )

        save_csv(
            f"{REPORT_DIR}/ranking.csv",
            ranking,
            RANKING_FIELDS,
        )

        save_csv(
            f"{REPORT_DIR}/folds.csv",
            fold_report,
            FOLD_FIELDS,
        )

        save_csv(
            f"{REPORT_DIR}/trades.csv",
            train_trades,
            TRADE_FIELDS,
        )

        # ====================================
        # HOLDOUT SELECTION
        #
        # Select using training data only.
        # Never select based on holdout PnL.
        # ====================================

        selected_name = ranking[0][
            "configuration"
        ]

        selected_config = next(
            config
            for config in CONFIGS
            if config["name"] == selected_name
        )

        print("\nSELECTED FROM TRAINING:")
        print(selected_name)

        if not ranking[0]["eligible"]:
            print(
                "WARNING: No configuration "
                "passed training eligibility."
            )

        # One untouched chronological
        # validation period.
        holdout_windows = [
            {
                "fold": "HOLDOUT",
                "valid_start": split,
                "valid_end": total,
            }
        ]

        holdout_rows = []
        holdout_trades = []

        for scenario, fee, slippage in [
            (
                "BASE",
                BASE_FEE,
                BASE_SLIPPAGE,
            ),
            (
                "STRESS",
                STRESS_FEE,
                STRESS_SLIPPAGE,
            ),
        ]:

            metrics, _ = evaluate(
                candles,
                indicators,
                htf_directions,
                holdout_windows,
                selected_config,
                scenario,
                fee,
                slippage,
            )

            holdout_rows.append({
                "configuration": selected_name,
                "scenario": scenario,
                "trades": metrics["trades"],
                "wins": metrics["wins"],
                "losses": metrics["losses"],
                "win_rate_pct": safe_round(
                    metrics["win_rate_pct"]
                ),
                "return_pct": safe_round(
                    metrics["return_pct"]
                ),
                "profit_factor": safe_round(
                    metrics["profit_factor"]
                ),
                "expectancy_usd": safe_round(
                    metrics["expectancy_usd"]
                ),
                "max_drawdown_pct": safe_round(
                    metrics["max_drawdown_pct"]
                ),
            })

            holdout_trades.extend(
                metrics["trade_log"]
            )

        save_csv(
            f"{REPORT_DIR}/holdout.csv",
            holdout_rows,
            HOLDOUT_FIELDS,
        )

        save_csv(
            f"{REPORT_DIR}/holdout_trades.csv",
            holdout_trades,
            TRADE_FIELDS,
        )

        # ====================================
        # RESULTS
        # ====================================

        print("\n" + "=" * 60)
        print("TOP V12 TRAINING RESULTS")
        print("=" * 60)

        for index, row in enumerate(
            ranking[:10],
            1,
        ):

            print(
                index,
                row["configuration"],
                "| Return:",
                row["return_pct"],
                "| Stress:",
                row["stress_return_pct"],
                "| PF:",
                row["profit_factor"],
                "| Eligible:",
                row["eligible"],
            )

        print("\n" + "=" * 60)
        print("V12 HOLDOUT RESULTS")
        print("=" * 60)

        for row in holdout_rows:

            print(
                row["scenario"],
                "| Trades:",
                row["trades"],
                "| Return:",
                row["return_pct"],
                "| PF:",
                row["profit_factor"],
            )

        print("\nV12 COMPLETED")
        print(f"{REPORT_DIR}/ranking.csv")
        print(f"{REPORT_DIR}/folds.csv")
        print(f"{REPORT_DIR}/trades.csv")
        print(f"{REPORT_DIR}/holdout.csv")
        print(f"{REPORT_DIR}/holdout_trades.csv")

    finally:

        v10.get_v10_signal = original_signal
        v11.ACTIVE_ATR = original_atr


if __name__ == "__main__":
    test_all()
