# ============================================================
# SPACE BAR AI TRADING
# TESTER V15.0
#
# ATR / ADX ROBUSTNESS RESEARCH ENGINE
#
# BTC 5M | BINANCE USDT FUTURES
# PAPER RESEARCH ONLY
#
# IMPORTANT:
# Historical diagnostic data has been inspected.
# It is NOT fresh independent OOS evidence.
# ============================================================

import os
import csv
import math

import tester_v10 as v10
import tester_v11 as v11
import tester_v14 as v14

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

REPORT_DIR = "reports/v15"

INITIAL_CAPITAL = 10000.0

TRAIN_RATIO = 0.80

MIN_TRADES = 30
MIN_POSITIVE_FOLDS = 3

MIN_BASE_PF = 1.10
MIN_STRESS_PF = 1.15

MIN_STRESS_POSITIVE_FOLDS = 3

SCENARIOS = [
    ("BASE", 0.00055, 0.00020),
    ("STRESS", 0.00100, 0.00050),
]

# ============================================================
# BASE CONFIGURATION
# ============================================================

BASE_CONFIG = {
    "name": "V15_BASELINE",

    "adx_min": 25,
    "adx_max": 999,

    "volume_mult": 0.0,

    "htf_filter": True,

    "stop": 0.006,
    "target": 0.012,

    "atr_min": 0.15,
    "atr_max": 0.30,

    "side": "BOTH",

    "signal_mode": "CROSS",
}

# ============================================================
# RESEARCH CONFIGURATIONS
#
# One-factor comparisons are included to reduce
# the temptation to optimize every parameter at once.
# ============================================================

def make_config(name, **changes):

    config = dict(BASE_CONFIG)

    config.update(changes)

    config["name"] = name

    return config


CONFIGS = [
    make_config("V15_BASELINE"),

    # ADX comparisons
    make_config(
        "ADX_25_30",
        adx_min=25,
        adx_max=30,
    ),

    make_config(
        "ADX_25_35",
        adx_min=25,
        adx_max=35,
    ),

    make_config(
        "ADX_30_35",
        adx_min=30,
        adx_max=35,
    ),

    # ATR comparisons
    make_config(
        "ATR_015_025",
        atr_min=0.15,
        atr_max=0.25,
    ),

    make_config(
        "ATR_020_025",
        atr_min=0.20,
        atr_max=0.25,
    ),

    make_config(
        "ATR_020_030",
        atr_min=0.20,
        atr_max=0.30,
    ),

    # Direction comparisons
    make_config(
        "LONG_ONLY",
        side="LONG",
    ),

    make_config(
        "SHORT_ONLY",
        side="SHORT",
    ),

    # Combined hypotheses
    make_config(
        "ADX25_30_ATR015_025",
        adx_min=25,
        adx_max=30,
        atr_min=0.15,
        atr_max=0.25,
    ),

    make_config(
        "ADX25_30_ATR020_025",
        adx_min=25,
        adx_max=30,
        atr_min=0.20,
        atr_max=0.25,
    ),

    make_config(
        "ADX25_35_ATR020_025",
        adx_min=25,
        adx_max=35,
        atr_min=0.20,
        atr_max=0.25,
    ),
]

# ============================================================
# CSV HELPERS
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
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


def safe_round(value):

    if value is None:
        return None

    value = float(value)

    if not math.isfinite(value):
        return None

    return round(value, 6)


# ============================================================
# V15 SIGNAL ENGINE
#
# Reuses the V11 signal rules.
# Adds an ADX upper bound.
#
# Signal is evaluated on a closed candle.
# V10 enters at the next candle open.
# ============================================================

ACTIVE_ATR = None


def v15_signal_adapter(
    candles,
    indicators,
    htf_directions,
    i,
    config,
):

    if ACTIVE_ATR is None:
        raise RuntimeError(
            "V15 ATR data is not initialized."
        )

    if i < 201 or i >= len(candles):
        return None

    adx = indicators["adx"][i]

    if adx is None:
        return None

    # Upper bound is exclusive.
    if adx >= config["adx_max"]:
        return None

    return v11.generate_signal(
        candles,
        indicators,
        htf_directions,
        ACTIVE_ATR,
        i,
        config,
    )


# ============================================================
# CONFIGURATION VALIDATION
# ============================================================

def validate_configs():

    names = set()

    for config in CONFIGS:

        name = config["name"]

        if name in names:
            raise RuntimeError(
                f"Duplicate configuration: {name}"
            )

        names.add(name)

        if not (
            0 <= config["adx_min"]
            < config["adx_max"]
        ):
            raise RuntimeError(
                f"Invalid ADX range: {name}"
            )

        if not (
            0 <= config["atr_min"]
            < config["atr_max"]
        ):
            raise RuntimeError(
                f"Invalid ATR range: {name}"
            )

        if config["side"] not in (
            "BOTH",
            "LONG",
            "SHORT",
        ):
            raise RuntimeError(
                f"Invalid side: {name}"
            )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(results):

    summary = v10.summarize(results)

    return {
        "trades": summary["trades"],
        "wins": summary["wins"],
        "losses": summary["losses"],

        "win_rate_pct": safe_round(
            summary["win_rate_pct"]
        ),

        "return_pct": safe_round(
            summary["return_pct"]
        ),

        "profit_factor": safe_round(
            summary["profit_factor"]
        ),

        "expectancy_usd": safe_round(
            summary["expectancy_usd"]
        ),

        "positive_folds": summary[
            "positive_folds"
        ],

        "total_folds": summary[
            "total_folds"
        ],

        "max_drawdown_pct": safe_round(
            summary["max_drawdown_pct"]
        ),

        "trade_log": summary["trade_log"],
    }


# ============================================================
# EVALUATION
# ============================================================

def evaluate(
    candles,
    indicators,
    htf_directions,
    windows,
    config,
    period,
):

    scenarios = {}

    fold_rows = []
    trade_rows = []

    for scenario, fee, slippage in SCENARIOS:

        results = []

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

            fold_metrics = calculate_metrics(
                [result]
            )

            fold_rows.append({
                "period": period,
                "configuration": config["name"],
                "scenario": scenario,
                "fold": window["fold"],

                "trades": fold_metrics["trades"],

                "win_rate_pct": fold_metrics[
                    "win_rate_pct"
                ],

                "return_pct": fold_metrics[
                    "return_pct"
                ],

                "profit_factor": fold_metrics[
                    "profit_factor"
                ],

                "max_drawdown_pct": fold_metrics[
                    "max_drawdown_pct"
                ],
            })

        metrics = calculate_metrics(results)

        scenarios[scenario] = metrics

        for trade in metrics["trade_log"]:

            trade_rows.append({
                "period": period,
                **trade,
            })

    return scenarios, fold_rows, trade_rows


# ============================================================
# ELIGIBILITY
#
# Selection uses TRAIN data only.
# ============================================================

def check_eligibility(base, stress):

    rejection = []

    if base["trades"] < MIN_TRADES:

        rejection.append(
            "INSUFFICIENT_TRADES"
        )

    if (
        base["positive_folds"]
        < MIN_POSITIVE_FOLDS
    ):

        rejection.append(
            "LOW_BASE_FOLD_CONSISTENCY"
        )

    if (
        stress["positive_folds"]
        < MIN_STRESS_POSITIVE_FOLDS
    ):

        rejection.append(
            "LOW_STRESS_FOLD_CONSISTENCY"
        )

    if base["return_pct"] <= 0:

        rejection.append(
            "NEGATIVE_BASE_RETURN"
        )

    if stress["return_pct"] <= 0:

        rejection.append(
            "NEGATIVE_STRESS_RETURN"
        )

    base_pf = base["profit_factor"]

    if (
        base_pf is None
        or base_pf < MIN_BASE_PF
    ):

        rejection.append(
            "LOW_BASE_PROFIT_FACTOR"
        )

    stress_pf = stress["profit_factor"]

    if (
        stress_pf is None
        or stress_pf < MIN_STRESS_PF
    ):

        rejection.append(
            "LOW_STRESS_PROFIT_FACTOR"
        )

    return rejection


# ============================================================
# MAIN
# ============================================================

def test_all():

    global ACTIVE_ATR

    print("=" * 60)
    print("SPACE BAR AI - TESTER V15.0")
    print("ATR / ADX ROBUSTNESS RESEARCH")
    print("=" * 60)

    validate_configs()

    candles = load_data(
        SYMBOL,
        TIMEFRAME,
    )

    v14.validate_history(candles)

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

    train_windows = walk_forward_windows(
        split
    )

    if len(train_windows) != 4:
        raise RuntimeError(
            "Expected four training folds."
        )

    for window in train_windows:

        if window["valid_end"] > split:
            raise RuntimeError(
                "Training overlaps diagnostic."
            )

    diagnostic_windows = [
        {
            "fold": "DIAGNOSTIC",
            "valid_start": split,
            "valid_end": total,
        }
    ]

    original_signal = v10.get_v10_signal

    original_atr = ACTIVE_ATR

    ACTIVE_ATR = atr_pct

    v10.get_v10_signal = v15_signal_adapter

    ranking = []
    all_folds = []
    all_trades = []

    try:

        # ----------------------------------------
        # TRAINING
        # ----------------------------------------

        for config in CONFIGS:

            scenarios, folds, trades = evaluate(
                candles,
                indicators,
                htf_directions,
                train_windows,
                config,
                "TRAIN",
            )

            base = scenarios["BASE"]
            stress = scenarios["STRESS"]

            rejection = check_eligibility(
                base,
                stress,
            )

            eligible = len(rejection) == 0

            ranking.append({
                "configuration": config["name"],

                "adx_min": config["adx_min"],
                "adx_max": config["adx_max"],

                "atr_min": config["atr_min"],
                "atr_max": config["atr_max"],

                "side": config["side"],

                "trades": base["trades"],

                "win_rate_pct": base[
                    "win_rate_pct"
                ],

                "base_return_pct": base[
                    "return_pct"
                ],

                "base_profit_factor": base[
                    "profit_factor"
                ],

                "stress_return_pct": stress[
                    "return_pct"
                ],

                "stress_profit_factor": stress[
                    "profit_factor"
                ],

                "base_positive_folds": base[
                    "positive_folds"
                ],

                "stress_positive_folds": stress[
                    "positive_folds"
                ],

                "max_drawdown_pct": stress[
                    "max_drawdown_pct"
                ],

                "eligible": eligible,

                "rejection_reasons": (
                    "|".join(rejection)
                    if rejection
                    else "PASS"
                ),
            })

            all_folds.extend(folds)
            all_trades.extend(trades)

            print(
                config["name"],
                "| Trades:", base["trades"],
                "| BASE:", base["return_pct"],
                "| STRESS:", stress["return_pct"],
                "| STRESS PF:",
                stress["profit_factor"],
                "| STRESS folds:",
                stress["positive_folds"],
                "| Eligible:", eligible,
                flush=True,
            )

        # ----------------------------------------
        # RANKING
        #
        # Rank eligible candidates first.
        # Within groups, prefer stronger
        # STRESS performance.
        # ----------------------------------------

        ranking.sort(
            key=lambda row: (
                row["eligible"],
                row["stress_positive_folds"],
                row["stress_profit_factor"]
                if row["stress_profit_factor"]
                is not None
                else -1,
                row["stress_return_pct"],
            ),
            reverse=True,
        )

        # ----------------------------------------
        # DIAGNOSTIC
        #
        # The baseline is always reported.
        # The top TRAIN candidate is also
        # reported if it differs.
        #
        # Diagnostic performance is NOT used
        # to change the ranking.
        # ----------------------------------------

        selected_names = ["V15_BASELINE"]

        if ranking:

            top_name = ranking[0][
                "configuration"
            ]

            if top_name not in selected_names:

                selected_names.append(
                    top_name
                )

        diagnostic_rows = []

        for name in selected_names:

            config = next(
                c for c in CONFIGS
                if c["name"] == name
            )

            scenarios, folds, trades = evaluate(
                candles,
                indicators,
                htf_directions,
                diagnostic_windows,
                config,
                "DIAGNOSTIC",
            )

            all_folds.extend(folds)
            all_trades.extend(trades)

            for scenario, metrics in scenarios.items():

                diagnostic_rows.append({
                    "configuration": name,
                    "scenario": scenario,

                    "trades": metrics["trades"],

                    "win_rate_pct": metrics[
                        "win_rate_pct"
                    ],

                    "return_pct": metrics[
                        "return_pct"
                    ],

                    "profit_factor": metrics[
                        "profit_factor"
                    ],

                    "max_drawdown_pct": metrics[
                        "max_drawdown_pct"
                    ],
                })

    finally:

        v10.get_v10_signal = original_signal

        ACTIVE_ATR = original_atr

    # ========================================================
    # SAVE REPORTS
    # ========================================================

    ranking_fields = [
        "configuration",
        "adx_min",
        "adx_max",
        "atr_min",
        "atr_max",
        "side",
        "trades",
        "win_rate_pct",
        "base_return_pct",
        "base_profit_factor",
        "stress_return_pct",
        "stress_profit_factor",
        "base_positive_folds",
        "stress_positive_folds",
        "max_drawdown_pct",
        "eligible",
        "rejection_reasons",
    ]

    fold_fields = [
        "period",
        "configuration",
        "scenario",
        "fold",
        "trades",
        "win_rate_pct",
        "return_pct",
        "profit_factor",
        "max_drawdown_pct",
    ]

    trade_fields = [
        "period",
        *v10.TRADE_FIELDS,
    ]

    diagnostic_fields = [
        "configuration",
        "scenario",
        "trades",
        "win_rate_pct",
        "return_pct",
        "profit_factor",
        "max_drawdown_pct",
    ]

    save_csv(
        f"{REPORT_DIR}/ranking.csv",
        ranking,
        ranking_fields,
    )

    save_csv(
        f"{REPORT_DIR}/folds.csv",
        all_folds,
        fold_fields,
    )

    save_csv(
        f"{REPORT_DIR}/trades.csv",
        all_trades,
        trade_fields,
    )

    save_csv(
        f"{REPORT_DIR}/diagnostic.csv",
        diagnostic_rows,
        diagnostic_fields,
    )

    print("\n" + "=" * 60)
    print("V15 RESEARCH RANKING")
    print("=" * 60)

    for index, row in enumerate(
        ranking,
        1,
    ):

        print(
            index,
            row["configuration"],
            "| STRESS:",
            row["stress_return_pct"],
            "| PF:",
            row["stress_profit_factor"],
            "| Eligible:",
            row["eligible"],
            "| Reasons:",
            row["rejection_reasons"],
        )

    print("\nV15 COMPLETED")

    print(f"{REPORT_DIR}/ranking.csv")
    print(f"{REPORT_DIR}/folds.csv")
    print(f"{REPORT_DIR}/trades.csv")
    print(f"{REPORT_DIR}/diagnostic.csv")

    print(
        "\nWARNING: Diagnostic results are "
        "historical and previously inspected."
    )

    print(
        "No strategy is approved for live trading."
    )


if __name__ == "__main__":
    test_all()
