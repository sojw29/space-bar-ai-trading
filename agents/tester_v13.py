# ============================================================
# SPACE BAR AI TRADING
# TESTER V13.0
#
# ADAPTIVE ATR + DIRECTION RESEARCH
# WALK-FORWARD + STRESS TEST
#
# BTC 5M | BINANCE USDT FUTURES
# PAPER RESEARCH ONLY
#
# IMPORTANT:
# Historical V12 holdout has already been inspected.
# V13 results on that period are NOT fresh OOS evidence.
# ============================================================

import csv
import os
import math
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

REPORT_DIR = "reports/v13"

TRAIN_RATIO = 0.80

MIN_TRADES = 30
MIN_POSITIVE_FOLDS = 3
MIN_PROFIT_FACTOR = 1.10

BASE_FEE = 0.00055
BASE_SLIPPAGE = 0.00020

STRESS_FEE = 0.00100
STRESS_SLIPPAGE = 0.00050

ATR_PERIOD = 14
ATR_AVG_PERIOD = 100


# ============================================================
# BASE CONFIGURATION
# ============================================================

BASE_CONFIG = {
    "name": "BASE",

    "adx_min": 25,
    "volume_mult": 0.0,
    "htf_filter": True,

    "stop": 0.006,
    "target": 0.012,

    "atr_min": 0.15,
    "atr_max": 0.30,

    "side": "BOTH",
    "signal_mode": "CROSS",

    # V13 custom setting
    "atr_mode": "ABSOLUTE",
}


CONFIGS = []


def add_config(name, **changes):

    config = deepcopy(BASE_CONFIG)

    config.update(changes)
    config["name"] = name

    CONFIGS.append(config)


# ============================================================
# V13 RESEARCH CANDIDATES
# ============================================================

# Preserve V12 winning candidate.
add_config(
    "V12_ATR_015_030",
)

# Relative ATR:
# 100 = current ATR equals trailing ATR average.
add_config(
    "REL_ATR_075_100",
    atr_mode="RELATIVE",
    atr_min=75.0,
    atr_max=100.0,
)

add_config(
    "REL_ATR_080_110",
    atr_mode="RELATIVE",
    atr_min=80.0,
    atr_max=110.0,
)

add_config(
    "REL_ATR_090_120",
    atr_mode="RELATIVE",
    atr_min=90.0,
    atr_max=120.0,
)

add_config(
    "REL_ATR_100_130",
    atr_mode="RELATIVE",
    atr_min=100.0,
    atr_max=130.0,
)

# Direction research.
add_config(
    "REL_LONG_ONLY",
    atr_mode="RELATIVE",
    atr_min=80.0,
    atr_max=110.0,
    side="LONG",
)

add_config(
    "REL_SHORT_ONLY",
    atr_mode="RELATIVE",
    atr_min=80.0,
    atr_max=110.0,
    side="SHORT",
)

# Trend strength research.
add_config(
    "REL_ADX20",
    atr_mode="RELATIVE",
    atr_min=80.0,
    atr_max=110.0,
    adx_min=20,
)

add_config(
    "REL_ADX30",
    atr_mode="RELATIVE",
    atr_min=80.0,
    atr_max=110.0,
    adx_min=30,
)

# Combined direction and trend.
add_config(
    "REL_LONG_ADX30",
    atr_mode="RELATIVE",
    atr_min=80.0,
    atr_max=110.0,
    adx_min=30,
    side="LONG",
)

add_config(
    "REL_SHORT_ADX30",
    atr_mode="RELATIVE",
    atr_min=80.0,
    atr_max=110.0,
    adx_min=30,
    side="SHORT",
)


# ============================================================
# REPORT FIELDS
# ============================================================

RANKING_FIELDS = [
    "configuration",
    "atr_mode",
    "side",
    "adx_min",

    "trades",
    "wins",
    "losses",

    "win_rate_pct",
    "return_pct",
    "profit_factor",

    "stress_return_pct",
    "stress_profit_factor",

    "positive_folds",
    "stress_positive_folds",
    "total_folds",

    "expectancy_usd",
    "average_win_usd",
    "average_loss_usd",
    "payoff_ratio",

    "max_drawdown_pct",

    "eligible",
    "rejection_reasons",
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


DIAGNOSTIC_FIELDS = [
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
    "validation_status",
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


# ============================================================
# ADAPTIVE ATR
# ============================================================

def calculate_relative_atr(
    atr_pct,
    average_period=100,
):

    """
    Relative ATR percentage:

        current ATR / trailing ATR average * 100

    Uses current and past ATR values only.

    100 = current ATR equals its trailing average.
    120 = current ATR is 20% above its average.

    No future candles are used.
    """

    result = [None] * len(atr_pct)

    if average_period < 1:
        raise ValueError(
            "ATR average period must be positive."
        )

    rolling_sum = 0.0
    valid_values = []

    for i, value in enumerate(atr_pct):

        if (
            value is None
            or not math.isfinite(float(value))
        ):
            valid_values.append(None)

        else:
            value = float(value)

            valid_values.append(value)
            rolling_sum += value

        if i >= average_period:

            old_value = valid_values[
                i - average_period
            ]

            if old_value is not None:
                rolling_sum -= old_value

        if i < average_period - 1:
            continue

        window = valid_values[
            i - average_period + 1:i + 1
        ]

        if any(
            item is None
            for item in window
        ):
            continue

        average = rolling_sum / average_period

        if average <= 0:
            continue

        current = valid_values[i]

        if current is None:
            continue

        result[i] = (
            current / average
        ) * 100.0

    return result


# ============================================================
# EVALUATION
# ============================================================

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


# ============================================================
# ELIGIBILITY
# ============================================================

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

    # New V13 stability condition:
    # Stress scenario must also show
    # positive performance in >= 3 folds.

    if (
        stress["positive_folds"]
        < MIN_POSITIVE_FOLDS
    ):

        reasons.append(
            "INSUFFICIENT_STRESS_POSITIVE_FOLDS"
        )

    return reasons


def build_ranking_row(
    config,
    base,
    stress,
):

    reasons = rejection_reasons(
        base,
        stress,
    )

    return {
        "configuration": config["name"],

        "atr_mode": config["atr_mode"],
        "side": config["side"],
        "adx_min": config["adx_min"],

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

        "positive_folds": base[
            "positive_folds"
        ],

        "stress_positive_folds": stress[
            "positive_folds"
        ],

        "total_folds": base[
            "total_folds"
        ],

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
    print("SPACE BAR AI - TESTER V13.0")
    print("ADAPTIVE ATR RESEARCH")
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

    # Original absolute ATR.
    atr_pct = v11.calculate_atr_pct(
        candles,
        period=ATR_PERIOD,
    )

    # Adaptive relative ATR.
    relative_atr = calculate_relative_atr(
        atr_pct,
        average_period=ATR_AVG_PERIOD,
    )

    total = len(candles)

    split = int(
        total * TRAIN_RATIO
    )

    if split < 1000:

        raise RuntimeError(
            "Insufficient training data."
        )

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
                "Training overlaps diagnostic period."
            )

    print(
        "Total candles:",
        total,
        flush=True,
    )

    print(
        "Training candles:",
        split,
        flush=True,
    )

    print(
        "Diagnostic candles:",
        total - split,
        flush=True,
    )

    print(
        "Training folds:",
        len(train_windows),
        flush=True,
    )

    print(
        "Configurations:",
        len(CONFIGS),
        flush=True,
    )

    ranking = []
    fold_report = []
    train_trades = []

    original_signal = v10.get_v10_signal
    original_atr = v11.ACTIVE_ATR

    # Preserve V11 signal generation.
    v10.get_v10_signal = v11.v11_signal_adapter

    try:

        # ====================================
        # TRAINING
        # ====================================

        for config in CONFIGS:

            # Switch the ATR input depending
            # on the configuration.
            #
            # V11 signal adapter checks
            # atr_min / atr_max against
            # ACTIVE_ATR values.

            if config["atr_mode"] == "RELATIVE":

                v11.ACTIVE_ATR = relative_atr

            else:

                v11.ACTIVE_ATR = atr_pct

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
        # RANKING
        # ====================================

        ranking.sort(
            key=lambda row: (
                row["eligible"],
                row["stress_positive_folds"],
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
        # HISTORICAL DIAGNOSTIC
        #
        # This final 20% period was already
        # inspected during V12 research.
        #
        # It is NOT a fresh untouched holdout.
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
                "passed V13 eligibility."
            )

        if (
            selected_config["atr_mode"]
            == "RELATIVE"
        ):

            v11.ACTIVE_ATR = relative_atr

        else:

            v11.ACTIVE_ATR = atr_pct

        diagnostic_windows = [
            {
                "fold": "DIAGNOSTIC",
                "valid_start": split,
                "valid_end": total,
            }
        ]

        diagnostic_rows = []
        diagnostic_trades = []

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
                diagnostic_windows,
                selected_config,
                scenario,
                fee,
                slippage,
            )

            diagnostic_rows.append({
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

                "validation_status":
                    "REUSED_HISTORICAL_DIAGNOSTIC",
            })

            diagnostic_trades.extend(
                metrics["trade_log"]
            )

        save_csv(
            f"{REPORT_DIR}/diagnostic.csv",
            diagnostic_rows,
            DIAGNOSTIC_FIELDS,
        )

        save_csv(
            f"{REPORT_DIR}/diagnostic_trades.csv",
            diagnostic_trades,
            TRADE_FIELDS,
        )

        # ====================================
        # SUMMARY
        # ====================================

        print("\n" + "=" * 60)
        print("TOP V13 TRAINING RESULTS")
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
                "| Stress folds:",
                row["stress_positive_folds"],
                "| Eligible:",
                row["eligible"],
            )

        print("\n" + "=" * 60)
        print("V13 HISTORICAL DIAGNOSTIC")
        print("=" * 60)

        print(
            "WARNING: This period is not "
            "fresh out-of-sample data."
        )

        for row in diagnostic_rows:

            print(
                row["scenario"],
                "| Trades:",
                row["trades"],
                "| Return:",
                row["return_pct"],
                "| PF:",
                row["profit_factor"],
            )

        print("\nV13 COMPLETED")

        print(f"{REPORT_DIR}/ranking.csv")
        print(f"{REPORT_DIR}/folds.csv")
        print(f"{REPORT_DIR}/trades.csv")
        print(f"{REPORT_DIR}/diagnostic.csv")
        print(f"{REPORT_DIR}/diagnostic_trades.csv")

    finally:

        v10.get_v10_signal = original_signal
        v11.ACTIVE_ATR = original_atr


if __name__ == "__main__":
    test_all()
