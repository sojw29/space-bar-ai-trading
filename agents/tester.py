# SPACE BAR AI TRADING
# TESTER V2.0 - BACKTEST ENGINE

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

FAST_EMA = 20
SLOW_EMA = 50

DATA_DIR = "data/history"
REPORT_DIR = "reports"

SYMBOLS = ["BTC", "ETH", "SOL"]
TIMEFRAMES = ["1", "5", "15"]


def load_data(coin, interval):
    path = f"{DATA_DIR}/{coin}_{interval}m.csv"

    if not os.path.exists(path):
        raise FileNotFoundError(path)

    candles = []

    with open(path, encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            candle = {
                "timestamp": int(row["timestamp"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"])
            }
            candles.append(candle)

    candles.sort(key=lambda x: x["timestamp"])

    if len(candles) < SLOW_EMA + 3:
        raise ValueError(f"Insufficient data: {path}")

    if len({
        c["timestamp"] for c in candles
    }) != len(candles):
        raise ValueError(f"Duplicate timestamps: {path}")

    return candles


def calculate_ema(prices, period):
    result = [None] * len(prices)

    if len(prices) < period:
        return result

    multiplier = 2 / (period + 1)
    previous = sum(prices[:period]) / period

    result[period - 1] = previous

    for i in range(period, len(prices)):
        previous = (
            prices[i] * multiplier
            + previous * (1 - multiplier)
        )
        result[i] = previous

    return result


def fill_price(price, side, is_entry):
    # Adverse slippage on both entry and exit.
    buy = (
        (side == "LONG" and is_entry)
        or (side == "SHORT" and not is_entry)
    )

    return price * (
        1 + SLIPPAGE if buy else 1 - SLIPPAGE
    )


def run_backtest(candles):
    closes = [c["close"] for c in candles]
    fast = calculate_ema(closes, FAST_EMA)
    slow = calculate_ema(closes, SLOW_EMA)

    equity = INITIAL_CAPITAL
    peak_equity = equity
    max_drawdown = 0.0

    position = None
    trades = []
    equity_curve = []

    def mark_equity(price):
        if position is None:
            return equity

        side = position["side"]
        qty = position["qty"]
        entry = position["entry"]

        direction = 1 if side == "LONG" else -1

        unrealized = direction * qty * (price - entry)
        estimated_exit_fee = qty * price * FEE_RATE

        return equity + unrealized - estimated_exit_fee

    def update_drawdown(timestamp, marked_equity):
        nonlocal peak_equity, max_drawdown

        peak_equity = max(peak_equity, marked_equity)

        if peak_equity > 0:
            drawdown = (
                peak_equity - marked_equity
            ) / peak_equity

            max_drawdown = max(max_drawdown, drawdown)

        equity_curve.append({
            "timestamp": timestamp,
            "equity": round(marked_equity, 4)
        })

    def close_position(timestamp, price, reason):
        nonlocal equity, position

        side = position["side"]
        entry = position["entry"]
        qty = position["qty"]

        exit_price = fill_price(
            price, side, False
        )

        direction = 1 if side == "LONG" else -1

        gross_pnl = direction * qty * (
            exit_price - entry
        )

        exit_fee = qty * exit_price * FEE_RATE

        # Entry fee was already deducted at entry.
        equity += gross_pnl - exit_fee

        net_pnl = (
            gross_pnl
            - position["entry_fee"]
            - exit_fee
        )

        trades.append({
            "side": side,
            "entry_time": position["time"],
            "exit_time": timestamp,
            "entry": round(entry, 6),
            "exit": round(exit_price, 6),
            "reason": reason,
            "quantity": round(qty, 8),
            "entry_fee": round(
                position["entry_fee"], 6
            ),
            "exit_fee": round(exit_fee, 6),
            "gross_pnl": round(gross_pnl, 6),
            "pnl": round(net_pnl, 6),
            "return_on_margin_pct": round(
                net_pnl / position["margin"] * 100,
                4
            )
        })

        position = None

    for i in range(SLOW_EMA + 1, len(candles)):
        candle = candles[i]

        # Signal confirmed on previous candle.
        previous = i - 1
        before = i - 2

        bullish_cross = (
            fast[before] is not None
            and slow[before] is not None
            and fast[before] <= slow[before]
            and fast[previous] > slow[previous]
        )

        bearish_cross = (
            fast[before] is not None
            and slow[before] is not None
            and fast[before] >= slow[before]
            and fast[previous] < slow[previous]
        )

        # Entry at current candle open.
        if position is None and equity > 0:
            if bullish_cross or bearish_cross:
                side = (
                    "LONG" if bullish_cross
                    else "SHORT"
                )

                entry = fill_price(
                    candle["open"], side, True
                )

                margin = equity * POSITION_SIZE
                qty = margin / entry
                entry_fee = qty * entry * FEE_RATE

                equity -= entry_fee

                position = {
                    "side": side,
                    "entry": entry,
                    "qty": qty,
                    "margin": margin,
                    "entry_fee": entry_fee,
                    "time": candle["timestamp"]
                }

        if position is not None:
            side = position["side"]
            entry = position["entry"]

            if side == "LONG":
                stop = entry * (1 - STOP_LOSS)
                target = entry * (1 + TAKE_PROFIT)

                # A gap through the stop fills at open.
                if candle["open"] <= stop:
                    close_position(
                        candle["timestamp"],
                        candle["open"],
                        "SL_GAP"
                    )
                elif candle["low"] <= stop:
                    close_position(
                        candle["timestamp"],
                        stop,
                        "SL"
                    )
                elif candle["high"] >= target:
                    close_position(
                        candle["timestamp"],
                        max(target, candle["open"]),
                        "TP"
                    )

            else:
                stop = entry * (1 + STOP_LOSS)
                target = entry * (1 - TAKE_PROFIT)

                if candle["open"] >= stop:
                    close_position(
                        candle["timestamp"],
                        candle["open"],
                        "SL_GAP"
                    )
                elif candle["high"] >= stop:
                    close_position(
                        candle["timestamp"],
                        stop,
                        "SL"
                    )
                elif candle["low"] <= target:
                    close_position(
                        candle["timestamp"],
                        min(target, candle["open"]),
                        "TP"
                    )

        # Conservative intrabar drawdown estimate.
        if position is not None:
            if position["side"] == "LONG":
                adverse_price = candle["low"]
            else:
                adverse_price = candle["high"]

            update_drawdown(
                candle["timestamp"],
                mark_equity(adverse_price)
            )

        update_drawdown(
            candle["timestamp"],
            mark_equity(candle["close"])
        )

    # Close remaining position at final close.
    if position is not None:
        last = candles[-1]

        close_position(
            last["timestamp"],
            last["close"],
            "END_OF_DATA"
        )

        update_drawdown(
            last["timestamp"],
            equity
        )

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]

    total_trades = len(trades)

    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))

    avg_win = (
        gross_profit / len(wins)
        if wins else 0
    )

    avg_loss = (
        gross_loss / len(losses)
        if losses else 0
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0 else None
    )

    avg_rr = (
        avg_win / avg_loss
        if avg_loss > 0 else None
    )

    win_rate = (
        len(wins) / total_trades * 100
        if total_trades else 0
    )

    total_return = (
        equity / INITIAL_CAPITAL - 1
    ) * 100

    return {
        "initial_capital": INITIAL_CAPITAL,
        "final_equity": round(equity, 2),
        "total_return_pct": round(
            total_return, 4
        ),
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "average_win": round(avg_win, 4),
        "average_loss": round(avg_loss, 4),
        "average_rr": (
            round(avg_rr, 4)
            if avg_rr is not None else None
        ),
        "profit_factor": (
            round(profit_factor, 4)
            if profit_factor is not None else None
        ),
        "max_drawdown_pct": round(
            max_drawdown * 100, 4
        ),
        "trades": trades,
        "equity_curve": equity_curve
    }


def save_report(coin, interval, result):
    os.makedirs(REPORT_DIR, exist_ok=True)

    base = f"{REPORT_DIR}/{coin}_{interval}m"

    report = {
        "symbol": coin,
        "timeframe": f"{interval}m",
        "strategy": "EMA_CROSSOVER_20_50",
        "version": "TESTER_V2.0",
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        **result
    }

    with open(
        f"{base}_backtest.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False
        )

    with open(
        f"{base}_trades.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as file:
        if result["trades"]:
            writer = csv.DictWriter(
                file,
                fieldnames=result["trades"][0].keys()
            )
            writer.writeheader()
            writer.writerows(result["trades"])

    print(f"Saved report: {base}")


def test_all():
    print("=" * 50)
    print("SPACE BAR AI - TESTER V2.0")
    print("=" * 50)

    os.makedirs(REPORT_DIR, exist_ok=True)

    summary = []
    failures = []

    for coin in SYMBOLS:
        for interval in TIMEFRAMES:
            try:
                candles = load_data(coin, interval)
                result = run_backtest(candles)

                save_report(coin, interval, result)

                summary.append({
                    "symbol": coin,
                    "timeframe": f"{interval}m",
                    "trades": result["total_trades"],
                    "win_rate_pct": result["win_rate_pct"],
                    "return_pct": result["total_return_pct"],
                    "profit_factor": result["profit_factor"],
                    "max_drawdown_pct": result[
                        "max_drawdown_pct"
                    ]
                })

                print(
                    f"{coin} {interval}m | "
                    f"Trades: {result['total_trades']} | "
                    f"Win: {result['win_rate_pct']}% | "
                    f"Return: {result['total_return_pct']}% | "
                    f"MDD: {result['max_drawdown_pct']}%"
                )

            except Exception as error:
                print(
                    f"ERROR {coin} {interval}m: {error}"
                )
                failures.append(f"{coin}_{interval}m")

    summary_path = f"{REPORT_DIR}/summary.csv"

    if summary:
        with open(
            summary_path,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=summary[0].keys()
            )
            writer.writeheader()
            writer.writerows(summary)

    if failures:
        raise RuntimeError(
            "Backtest failed: "
            + ", ".join(failures)
        )

    print("\nBacktest finished successfully.")


if __name__ == "__main__":
    test_all()
