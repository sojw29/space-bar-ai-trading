# ============================================================
# SPACE BAR AI TRADING
# HISTORY V7.0 - BINANCE USDT FUTURES
# LONG-TERM MARKET DATA
# PAPER RESEARCH ONLY
# ============================================================

import csv
import io
import os
import time
import zipfile
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
TIMEFRAMES = [1, 5, 15]

DATA_DIR = "data/history"

BASE_URL = (
    "https://data.binance.vision/data/futures/um/monthly/klines"
)

DAYS_TO_COLLECT = 365
MAX_MONTHS_PER_RUN = 3
MAX_RETRIES = 3

os.makedirs(DATA_DIR, exist_ok=True)


def month_start(dt):
    return datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)


def previous_month(dt):
    return month_start(dt) - timedelta(days=1)


def download_month(symbol, year, month):
    filename = f"{symbol}-1m-{year}-{month:02d}.zip"
    url = f"{BASE_URL}/{symbol}/1m/{filename}"

    for attempt in range(MAX_RETRIES):
        try:
            request = Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            with urlopen(request, timeout=90) as response:
                content = response.read()

            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                csv_name = next(
                    name for name in archive.namelist()
                    if name.endswith(".csv")
                )

                with archive.open(csv_name) as file:
                    reader = csv.reader(
                        io.TextIOWrapper(file, encoding="utf-8")
                    )
                    rows = list(reader)

            print(
                f"Downloaded {symbol} {year}-{month:02d}: "
                f"{len(rows)} rows",
                flush=True
            )

            return rows

        except (
            HTTPError,
            URLError,
            TimeoutError,
            zipfile.BadZipFile,
            StopIteration,
            OSError
        ) as error:
            print(
                f"Retry {attempt + 1}/{MAX_RETRIES}: {error}",
                flush=True
            )

            if attempt < MAX_RETRIES - 1:
                time.sleep(3)

    raise RuntimeError(
        f"Failed to download {symbol} {year}-{month:02d}"
    )


def load_existing(symbol):
    short_symbol = symbol.replace("USDT", "")
    path = f"{DATA_DIR}/{short_symbol}_1m.csv"

    candles = {}

    if not os.path.exists(path):
        return candles

    with open(path, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                timestamp = int(float(row["timestamp"]))

                candles[timestamp] = [
                    timestamp,
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                    float(row["volume"])
                ]
            except (ValueError, KeyError, TypeError):
                continue

    print(
        f"Loaded {symbol}: {len(candles)} existing candles",
        flush=True
    )

    return candles


def save_csv(symbol, timeframe, candles):
    short_symbol = symbol.replace("USDT", "")
    path = f"{DATA_DIR}/{short_symbol}_{timeframe}m.csv"

    with open(path, "w", newline="", encoding="utf-8") as file:
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


def aggregate_candles(one_minute, timeframe):
    buckets = {}
    seconds = timeframe * 60

    for candle in one_minute:
        timestamp, op, hi, lo, cl, vol = candle
        bucket = (timestamp // seconds) * seconds

        if bucket not in buckets:
            buckets[bucket] = [
                bucket, op, hi, lo, cl, vol, 1
            ]
        else:
            item = buckets[bucket]
            item[2] = max(item[2], hi)
            item[3] = min(item[3], lo)
            item[4] = cl
            item[5] += vol
            item[6] += 1

    return [
        buckets[key][:6]
        for key in sorted(buckets)
        if buckets[key][6] == timeframe
    ]


def collect_symbol(symbol):
    print(f"\nCollecting {symbol}", flush=True)

    candles = load_existing(symbol)

    now = datetime.now(timezone.utc)
    target_start = int(
        (now - timedelta(days=DAYS_TO_COLLECT)).timestamp()
    )
    current_minute = int(now.timestamp() // 60) * 60

    month = previous_month(now)
    months_downloaded = 0

    while months_downloaded < MAX_MONTHS_PER_RUN:
        year = month.year
        month_number = month.month

        month_timestamp = int(
            month_start(month).timestamp()
        )

        if month_timestamp < target_start - 31 * 86400:
            break

        rows = download_month(
            symbol,
            year,
            month_number
        )

        for row in rows:
            try:
                timestamp_ms = int(row[0])

                # Normalize milliseconds or microseconds.
                if timestamp_ms > 10**14:
                    timestamp = timestamp_ms // 1000000
                else:
                    timestamp = timestamp_ms // 1000

                if not (
                    target_start <= timestamp < current_minute
                ):
                    continue

                candle = [
                    timestamp,
                    float(row[1]),
                    float(row[2]),
                    float(row[3]),
                    float(row[4]),
                    float(row[5])
                ]

                if (
                    candle[1] <= 0
                    or candle[2] < max(candle[1], candle[4])
                    or candle[3] > min(candle[1], candle[4])
                    or candle[5] < 0
                ):
                    continue

                candles[timestamp] = candle

            except (ValueError, IndexError):
                continue

        months_downloaded += 1
        month = previous_month(month)

    one_minute = [
        candles[key]
        for key in sorted(candles)
        if target_start <= key < current_minute
    ]

    if not one_minute:
        raise RuntimeError(
            f"No market data collected for {symbol}"
        )

    save_csv(symbol, 1, one_minute)

    for timeframe in [5, 15]:
        aggregated = aggregate_candles(
            one_minute,
            timeframe
        )
        save_csv(symbol, timeframe, aggregated)

    print(
        f"{symbol} completed: {len(one_minute)} candles",
        flush=True
    )


def main():
    print("SPACE BAR AI HISTORY V7.0", flush=True)

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

    print("\nHISTORY V7 COMPLETED", flush=True)


if __name__ == "__main__":
    main()
