# ==========================================
# SPACE BAR AI TRADING
# TESTER V3.0
# MULTI-STRATEGY BACKTEST ENGINE
# PAPER RESEARCH ONLY
# ==========================================

import csv
import json
import os
from datetime import datetime, timezone

INITIAL_CAPITAL = 10000.0

FEE_RATE = 0.00055
SLIPPAGE = 0.0002
POSITION_SIZE = 0.10

STOP_LOSS = 0.006
TAKE_PROFIT = 0.012

DATA_DIR = "data/history"
REPORT_DIR = "reports"

SYMBOLS = ["BTC", "ETH", "SOL"]
TIMEFRAMES = ["1", "5", "15"]

TRAIN_RATIO = 0.70
MIN_CANDLES = 300

STRATEGIES = [
    "EMA_CROSS",
    "TREND_ADX",
    "VOLUME_BREAKOUT",
    "EMA_PULLBACK",
    "LIQUIDITY_SWEEP"
]


# ==========================================
# 1. LOAD MARKET DATA
# ==========================================

def load_data(symbol, timeframe):

    path = (
        f"{DATA_DIR}/"
        f"{symbol}_{timeframe}m.csv"
    )

    if not os.path.exists(path):
        print("Missing:", path)
        return []

    candles = []

    with open(
        path,
        "r",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            try:
                candles.append({
                    "timestamp": int(
                        row["timestamp"]
                    ),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"])
                })

            except (ValueError, KeyError):
                continue

    candles.sort(
        key=lambda x: x["timestamp"]
    )

    # Remove duplicate timestamps
    unique = {}

    for candle in candles:
        unique[candle["timestamp"]] = candle

    return list(unique.values())


# ==========================================
# 2. INDICATORS
# ==========================================

def ema(values, period):

    result = [None] * len(values)

    if len(values) < period:
        return result

    first = sum(values[:period]) / period

    result[period - 1] = first

    multiplier = 2 / (period + 1)
    previous = first

    for i in range(period, len(values)):

        previous = (
            values[i] * multiplier
            + previous * (1 - multiplier)
        )

        result[i] = previous

    return result


def sma(values, period):

    result = [None] * len(values)

    running_sum = 0.0

    for i, value in enumerate(values):

        running_sum += value

        if i >= period:
            running_sum -= values[i - period]

        if i >= period - 1:
            result[i] = running_sum / period

    return result


def calculate_adx(candles, period=14):

    n = len(candles)

    adx = [None] * n

    if n < period * 2 + 1:
        return adx

    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n

    for i in range(1, n):

        current = candles[i]
        previous = candles[i - 1]

        up = (
            current["high"]
            - previous["high"]
        )

        down = (
            previous["low"]
            - current["low"]
        )

        plus_dm[i] = (
            up if up > down and up > 0
            else 0.0
        )

        minus_dm[i] = (
            down if down > up and down > 0
            else 0.0
        )

        tr[i] = max(
            current["high"] - current["low"],
            abs(
                current["high"]
                - previous["close"]
            ),
            abs(
                current["low"]
                - previous["close"]
            )
        )

    sm_tr = sum(tr[1:period + 1])
    sm_plus = sum(plus_dm[1:period + 1])
    sm_minus = sum(minus_dm[1:period + 1])

    dx = [None] * n

    for i in range(period, n):

        if i > period:

            sm_tr = (
                sm_tr
                - sm_tr / period
                + tr[i]
            )

            sm_plus = (
                sm_plus
                - sm_plus / period
                + plus_dm[i]
            )

            sm_minus = (
                sm_minus
                - sm_minus / period
                + minus_dm[i]
            )

        if sm_tr <= 0:
            dx[i] = 0.0
            continue

        plus_di = 100 * sm_plus / sm_tr
        minus_di = 100 * sm_minus / sm_tr

        denominator = plus_di + minus_di

        dx[i] = (
            100 * abs(plus_di - minus_di)
            / denominator
            if denominator > 0
            else 0.0
        )

    first_adx_index = period * 2 - 1

    adx[first_adx_index] = (
        sum(
            dx[period:first_adx_index + 1]
        ) / period
    )

    for i in range(first_adx_index + 1, n):

        adx[i] = (
            adx[i - 1] * (period - 1)
            + dx[i]
        ) / period

    return adx


# ==========================================
# 3. PREPARE INDICATORS
# ==========================================

def prepare(candles):

    closes = [
        c["close"] for c in candles
    ]

    volumes = [
        c["volume"] for c in candles
    ]

    return {
        "ema20": ema(closes, 20),
        "ema50": ema(closes, 50),
        "ema200": ema(closes, 200),
        "vol20": sma(volumes, 20),
        "adx": calculate_adx(candles, 14)
    }


# ==========================================
# 4. STRATEGY SIGNALS
# ==========================================

def get_signal(
    strategy,
    candles,
    indicators,
    i
):

    if i < 201:
        return None

    c = candles[i]
    p = candles[i - 1]

    e20 = indicators["ema20"]
    e50 = indicators["ema50"]
    e200 = indicators["ema200"]

    vol20 = indicators["vol20"]
    adx = indicators["adx"]

    if strategy == "EMA_CROSS":

        if (
            e20[i - 1] <= e50[i - 1]
            and e20[i] > e50[i]
        ):
            return "LONG"

        if (
            e20[i - 1] >= e50[i - 1]
            and e20[i] < e50[i]
        ):
            return "SHORT"

    elif strategy == "TREND_ADX":

        if adx[i] is None or adx[i] < 25:
            return None

        if (
            e50[i] > e200[i]
            and c["close"] > e50[i]
            and p["close"] <= e50[i - 1]
        ):
            return "LONG"

        if (
            e50[i] < e200[i]
            and c["close"] < e50[i]
            and p["close"] >= e50[i - 1]
        ):
            return "SHORT"

    elif strategy == "VOLUME_BREAKOUT":

        if vol20[i] is None:
            return None

        if c["volume"] < vol20[i] * 1.5:
            return None

        previous_high = max(
            x["high"]
            for x in candles[i - 20:i]
        )

        previous_low = min(
            x["low"]
            for x in candles[i - 20:i]
        )

        if (
            c["close"] > previous_high
            and c["close"] > e200[i]
        ):
            return "LONG"

        if (
            c["close"] < previous_low
            and c["close"] < e200[i]
        ):
            return "SHORT"

    elif strategy == "EMA_PULLBACK":

        if (
            e50[i] > e200[i]
            and c["low"] <= e50[i]
            and c["close"] > e50[i]
            and c["close"] > c["open"]
        ):
            return "LONG"

        if (
            e50[i] < e200[i]
            and c["high"] >= e50[i]
            and c["close"] < e50[i]
            and c["close"] < c["open"]
        ):
            return "SHORT"

    elif strategy == "LIQUIDITY_SWEEP":

        previous_high = max(
            x["high"]
            for x in candles[i - 10:i]
        )

        previous_low = min(
            x["low"]
            for x in candles[i - 10:i]
        )

        if (
            c["low"] < previous_low
            and c["close"] > previous_low
            and c["close"] > c["open"]
        ):
            return "LONG"

        if (
            c["high"] > previous_high
            and c["close"] < previous_high
            and c["close"] < c["open"]
        ):
            return "SHORT"

    return None


# ==========================================
# 5. BACKTEST ENGINE
# ==========================================

def run_backtest(
    candles,
    indicators,
    strategy,
    start,
    end
):

    equity = INITIAL_CAPITAL
    peak = equity
    max_drawdown = 0.0

    position = None
    trades = []

    def close_position(
        position,
        exit_price,
        exit_time,
        reason,
        equity
    ):

        side = position["side"]
        entry = position["entry"]
        amount = position["amount"]

        if side == "LONG":
            gross_return = exit_price / entry - 1
        else:
            gross_return = entry / exit_price - 1

        fees = amount * FEE_RATE * 2

        pnl = amount * gross_return - fees

        equity += pnl

        trade = {
            "side": side,
            "entry_time": position["time"],
            "exit_time": exit_time,
            "entry": round(entry, 6),
            "exit": round(exit_price, 6),
            "reason": reason,
            "pnl": round(pnl, 6)
        }

        return equity, trade

    for i in range(start, end):

        candle = candles[i]

        # Existing position:
        # stop/target are checked from
        # the candle AFTER entry.

        if position is not None:

            side = position["side"]
            entry = position["entry"]

            if side == "LONG":

                stop = entry * (1 - STOP_LOSS)
                target = entry * (1 + TAKE_PROFIT)

                if candle["low"] <= stop:

                    exit_price = (
                        stop * (1 - SLIPPAGE)
                    )
                    reason = "SL"

                elif candle["high"] >= target:

                    exit_price = (
                        target * (1 - SLIPPAGE)
                    )
                    reason = "TP"

                else:
                    exit_price = None

            else:

                stop = entry * (1 + STOP_LOSS)
                target = entry * (1 - TAKE_PROFIT)

                if candle["high"] >= stop:

                    exit_price = (
                        stop * (1 + SLIPPAGE)
                    )
                    reason = "SL"

                elif candle["low"] <= target:

                    exit_price = (
                        target * (1 + SLIPPAGE)
                    )
                    reason = "TP"

                else:
                    exit_price = None

            if exit_price is not None:

                equity, trade = close_position(
                    position,
                    exit_price,
                    candle["timestamp"],
                    reason,
                    equity
                )

                trades.append(trade)
                position = None

                peak = max(peak, equity)

                if peak > 0:

                    dd = (
                        (peak - equity)
                        / peak
                    )

                    max_drawdown = max(
                        max_drawdown,
                        dd
                    )

            # Do not open a new position
            # on the same candle.
            continue

        if equity <= 0:
            break

        # Signal uses only the previous
        # completed candle.
        signal = get_signal(
            strategy,
            candles,
            indicators,
            i - 1
        )

        if signal is None:
            continue

        entry_price = candle["open"]

        if signal == "LONG":
            entry_price *= 1 + SLIPPAGE
        else:
            entry_price *= 1 - SLIPPAGE

        position = {
            "side": signal,
            "entry": entry_price,
            "amount": equity * POSITION_SIZE,
            "time": candle["timestamp"]
        }

    # Close remaining position at
    # the last available candle.

    if position is not None:

        last = candles[end - 1]

        if position["side"] == "LONG":

            exit_price = (
                last["close"] * (1 - SLIPPAGE)
            )

        else:

            exit_price = (
                last["close"] * (1 + SLIPPAGE)
            )

        equity, trade = close_position(
            position,
            exit_price,
            last["timestamp"],
            "END",
            equity
        )

        trades.append(trade)

        peak = max(peak, equity)

        if peak > 0:

            max_drawdown = max(
                max_drawdown,
                (peak - equity) / peak
            )

    # ======================================
    # PERFORMANCE
    # ======================================

    wins = [
        t for t in trades
        if t["pnl"] > 0
    ]

    losses = [
        t for t in trades
        if t["pnl"] < 0
    ]

    total = len(trades)

    gross_profit = sum(
        t["pnl"] for t in wins
    )

    gross_loss = abs(sum(
        t["pnl"] for t in losses
    ))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else None
    )

    win_rate = (
        len(wins) / total * 100
        if total
        else 0.0
    )

    total_return = (
        equity / INITIAL_CAPITAL - 1
    ) * 100

    return {
        "trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 4),
        "return_pct": round(total_return, 4),
        "profit_factor": (
            round(profit_factor, 4)
            if profit_factor is not None
            else None
        ),
        "max_drawdown_pct": round(
            max_drawdown * 100,
            4
        ),
        "final_equity": round(equity, 4),
        "trade_log": trades
    }


# ==========================================
# 6. SAVE REPORTS
# ==========================================

def save_csv(path, rows, fields):

    os.makedirs(
        os.path.dirname(path),
        exist_ok=True
    )

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(rows)


def save_json(path, data):

    os.makedirs(
        os.path.dirname(path),
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


# ==========================================
# 7. MAIN
# ==========================================

def test_all():

    print("=" * 50)
    print("SPACE BAR AI - TESTER V3.0")
    print("=" * 50)

    os.makedirs(
        REPORT_DIR,
        exist_ok=True
    )

    summary = []

    for symbol in SYMBOLS:

        for timeframe in TIMEFRAMES:

            candles = load_data(
                symbol,
                timeframe
            )

            if len(candles) < MIN_CANDLES:

                print(
                    "Insufficient data:",
                    symbol,
                    timeframe
                )

                continue

            indicators = prepare(candles)

            split = int(
                len(candles) * TRAIN_RATIO
            )

            # Training and validation
            # are separate chronological
            # execution periods.
            #
            # Indicators may use earlier
            # candles as historical context.

            periods = [
                ("TRAIN", 201, split),
                ("VALIDATION", split, len(candles))
            ]

            for strategy in STRATEGIES:

                for (
                    period_name,
                    start,
                    end
                ) in periods:

                    if end <= start:
                        continue

                    result = run_backtest(
                        candles,
                        indicators,
                        strategy,
                        start,
                        end
                    )

                    row = {
                        "symbol": symbol,
                        "timeframe": (
                            timeframe + "m"
                        ),
                        "strategy": strategy,
                        "period": period_name,
                        "trades": result["trades"],
                        "win_rate_pct": (
                            result["win_rate_pct"]
                        ),
                        "return_pct": (
                            result["return_pct"]
                        ),
                        "profit_factor": (
                            result["profit_factor"]
                        ),
                        "max_drawdown_pct": (
                            result["max_drawdown_pct"]
                        )
                    }

                    summary.append(row)

                    report_name = (
                        f"{symbol}_{timeframe}m_"
                        f"{strategy}_{period_name}"
                    )

                    save_json(
                        f"{REPORT_DIR}/"
                        f"{report_name}.json",
                        {
                            "created_at": (
                                datetime.now(
                                    timezone.utc
                                ).isoformat()
                            ),
                            **row,
                            "trade_log": (
                                result["trade_log"]
                            )
                        }
                    )

                    print(
                        f"{symbol} {timeframe}m "
                        f"{strategy} {period_name} | "
                        f"Trades: {result['trades']} | "
                        f"Win: {result['win_rate_pct']}% | "
                        f"Return: {result['return_pct']}% | "
                        f"PF: {result['profit_factor']}"
                    )

    fields = [
        "symbol",
        "timeframe",
        "strategy",
        "period",
        "trades",
        "win_rate_pct",
        "return_pct",
        "profit_factor",
        "max_drawdown_pct"
    ]

    save_csv(
        f"{REPORT_DIR}/summary.csv",
        summary,
        fields
    )

    # Rank validation results separately.
    validation = [
        row for row in summary
        if row["period"] == "VALIDATION"
    ]

    # Avoid treating tiny samples as
    # strong evidence of profitability.
    eligible = [
        row for row in validation
        if row["trades"] >= 10
    ]

    eligible.sort(
        key=lambda row: (
            row["profit_factor"]
            if row["profit_factor"] is not None
            else -1
        ),
        reverse=True
    )

    save_csv(
        f"{REPORT_DIR}/ranking.csv",
        eligible,
        fields
    )

    print("\n" + "=" * 50)
    print("VALIDATION RANKING")
    print("=" * 50)

    for index, row in enumerate(
        eligible[:10],
        start=1
    ):

        print(
            f"{index}. "
            f"{row['symbol']} "
            f"{row['timeframe']} "
            f"{row['strategy']} | "
            f"Trades: {row['trades']} | "
            f"Return: {row['return_pct']}% | "
            f"PF: {row['profit_factor']}"
        )

    if not summary:
        raise RuntimeError(
            "No backtest results generated."
        )

    print("\nTESTER V3.0 COMPLETED")
    print("Summary: reports/summary.csv")
    print("Ranking: reports/ranking.csv")


if __name__ == "__main__":
    test_all()
