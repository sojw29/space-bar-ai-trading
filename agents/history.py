# SPACE BAR AI TRADING
# HISTORY V2.0 - PUBLIC TRADE DATA

import csv
import gzip
import io
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
TIMEFRAMES = [1, 5, 15]
TARGET_CANDLES = 10000

DATA_DIR = "data/history"
BASE_URL = "https://public.bybit.com/trading"

# Download recent daily trade archives.
# 12 days is enough for 10,000 1-minute candles.
MAX_DAYS = 12

os.makedirs(DATA_DIR, exist_ok=True)


def download_day(symbol, day):
    date_str = day.strftime("%Y-%m-%d")
    filename = f"{symbol}{date_str}.csv.gz"
    url = f"{BASE_URL}/{symbol}/{filename}"

    request = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    for attempt in range(3):
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()

        except (HTTPError, URLError, TimeoutError) as error:
            print(
                f"Download attempt {attempt + 1} failed: "
                f"{symbol} {date_str}: {error}",
                flush=True
            )
            if attempt < 2:
                time.sleep(2)

    return None


def parse_trades(compressed_data):
    candles = {}

    with gzip.GzipFile(
        fileobj=io.BytesIO(compressed_data)
    ) as gz:
        text = io.TextIOWrapper(gz, encoding="utf-8")
        reader = csv.DictReader(text)

        for row in reader:
            try:
                timestamp = float(row["timestamp"])
                price = float(row["price"])
                volume = float(row["size"])

                minute = int(timestamp // 60) * 60

                if minute not in candles:
                    candles[minute] = [
                        minute,
                        price,
                        price,
                        price,
                        price,
                        volume
                    ]
                else:
                    candle = candles[minute]
                    candle[2] = max(candle[2], price)
                    candle[3] = min(candle[3], price)
                    candle[4] = price
                    candle[5] += volume

            except (KeyError, ValueError, TypeError):
                continue

    return candles


def aggregate_candles(one_minute, timeframe):
    result = {}

    for candle in one_minute:
        timestamp, op, hi, lo, cl, vol = candle
        bucket = (timestamp // (timeframe * 60)) * (
            timeframe * 60
        )

        if bucket not in result:
            result[bucket] = [
                bucket, op, hi, lo, cl, vol
            ]
        else:
            item = result[bucket]
            item[2] = max(item[2], hi)
            item[3] = min(item[3], lo)
            item[4] = cl
            item[5] += vol

    return [result[key] for key in sorted(result)]


def save_csv(symbol, timeframe, candles):
    short_symbol = symbol.replace("USDT", "")
    path = (
        f"{DATA_DIR}/"
        f"{short_symbol}_{timeframe}m.csv"
    )

    candles = candles[-TARGET_CANDLES:]

    with open(path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ])
        writer.writerows(candles)

    print(
        f"Saved {path}: {len(candles)} candles",
        flush=True
    )


def collect_symbol(symbol):
    print(f"\nCollecting {symbol}", flush=True)

    all_candles = {}
    today = datetime.now(timezone.utc).date()

    # Exclude the current, incomplete UTC day.
    for days_back in range(1, MAX_DAYS + 1):
        day = today - timedelta(days=days_back)

        print(
            f"Downloading {symbol} {day}",
            flush=True
        )

        compressed = download_day(symbol, day)

        if compressed is None:
            continue

        daily_candles = parse_trades(compressed)
        all_candles.update(daily_candles)

        print(
            f"Collected {len(all_candles)} minutes",
            flush=True
        )

        if len(all_candles) >= TARGET_CANDLES:
            break

    one_minute = [
        all_candles[key]
        for key in sorted(all_candles)
    ]

    if len(one_minute) < TARGET_CANDLES:
        raise RuntimeError(
            f"{symbol}: insufficient 1m data "
            f"({len(one_minute)}/{TARGET_CANDLES})"
        )

    for timeframe in TIMEFRAMES:
        if timeframe == 1:
            candles = one_minute
        else:
            candles = aggregate_candles(
                one_minute, timeframe
            )

        if not candles:
            raise RuntimeError(
                f"No candles for {symbol} {timeframe}m"
            )

        save_csv(symbol, timeframe, candles)


def main():
    print("SPACE BAR AI HISTORY V2.0", flush=True)

    failures = []

    for symbol in SYMBOLS:
        try:
            collect_symbol(symbol)
        except Exception as error:
            print(
                f"ERROR {symbol}: {error}",
                flush=True
            )
            failures.append(symbol)

    if failures:
        raise RuntimeError(
            "History collection failed: "
            + ", ".join(failures)
        )

    print("\nHistory collection completed!", flush=True)


if __name__ == "__main__":
    main()
