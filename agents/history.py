# ============================================================
# SPACE BAR AI TRADING
# HISTORY V7.1 - BINANCE USDT FUTURES
# 365-DAY HISTORICAL DATA
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
BASE_URL = "https://data.binance.vision/data/futures/um"

DAYS_TO_COLLECT = 365
MAX_RETRIES = 3

os.makedirs(DATA_DIR, exist_ok=True)


def download_zip(url):
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            request = Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            with urlopen(request, timeout=120) as response:
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
                    return list(reader)

        except HTTPError as error:
            # Recent daily archives may not be published yet.
            if error.code == 404:
                return None

            last_error = error

        except (
            URLError,
            TimeoutError,
            zipfile.BadZipFile,
            StopIteration,
            OSError,
        ) as error:
            last_error = error

        print(
            f"Retry {attempt + 1}/{MAX_RETRIES}: "
            f"{last_error}",
            flush=True
        )

        if attempt < MAX_RETRIES - 1:
            time.sleep(3)

    raise RuntimeError(
        f"Download failed: {url} | {last_error}"
    )


def normalize_timestamp(value):
    timestamp = int(value)

    if timestamp > 10**14:
        return timestamp // 1000000

    return timestamp // 1000


def add_rows(candles, rows, start_ts, end_ts):
    if rows is None:
        return 0

    added = 0

    for row in rows:
        try:
            timestamp = normalize_timestamp(row[0])

            if not start_ts <= timestamp < end_ts:
                continue

            op = float(row[1])
            hi = float(row[2])
            lo = float(row[3])
            cl = float(row[4])
            vol = float(row[5])

            if timestamp % 60 != 0:
                continue

            if min(op, hi, lo, cl) <= 0:
                continue

            if hi < max(op, cl, lo):
                continue

            if lo > min(op, cl):
                continue

            if vol < 0:
                continue

            if timestamp not in candles:
                added += 1

            candles[timestamp] = [
                timestamp, op, hi, lo, cl, vol
            ]

        except (ValueError, TypeError, IndexError):
            continue

    return added


def month_starts(start, end):
    current = datetime(
        start.year, start.month, 1,
        tzinfo=timezone.utc
    )

    while current < end:
        yield current

        if current.month == 12:
            current = datetime(
                current.year + 1, 1, 1,
                tzinfo=timezone.utc
            )
        else:
            current = datetime(
                current.year, current.month + 1, 1,
                tzinfo=timezone.utc
            )


def save_csv(symbol, timeframe, candles):
    short_symbol = symbol.replace("USDT", "")

    path = (
        f"{DATA_DIR}/{short_symbol}_{timeframe}m.csv"
    )

    with open(
        path, "w", newline="", encoding="utf-8"
    ) as file:
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
    result = {}
    interval = timeframe * 60

    for candle in one_minute:
        timestamp, op, hi, lo, cl, vol = candle

        bucket = (timestamp // interval) * interval

        if bucket not in result:
            result[bucket] = [
                bucket, op, hi, lo, cl, vol, 1
            ]
        else:
            item = result[bucket]
            item[2] = max(item[2], hi)
            item[3] = min(item[3], lo)
            item[4] = cl
            item[5] += vol
            item[6] += 1

    return [
        result[key][:6]
        for key in sorted(result)
        if result[key][6] == timeframe
    ]


def collect_symbol(symbol, start, end):
    print(f"\nCollecting {symbol}", flush=True)

    candles = {}

    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())

    # 1. Download completed monthly archives.
    for month in month_starts(start, end):
        next_month = (
            datetime(month.year + 1, 1, 1, tzinfo=timezone.utc)
            if month.month == 12
            else datetime(
                month.year, month.month + 1, 1,
                tzinfo=timezone.utc
            )
        )

        # The current month is handled through daily files.
        if next_month > end:
            continue

        filename = (
            f"{symbol}-1m-{month.year}-"
            f"{month.month:02d}.zip"
        )

        url = (
            f"{BASE_URL}/monthly/klines/"
            f"{symbol}/1m/{filename}"
        )

        rows = download_zip(url)

        if rows is None:
            print(
                f"Monthly archive unavailable: {filename}",
                flush=True
            )
            continue

        added = add_rows(
            candles, rows, start_ts, end_ts
        )

        print(
            f"Monthly {filename}: +{added}",
            flush=True
        )

    # 2. Fill missing days from daily archives.
    current_day = datetime(
        start.year, start.month, start.day,
        tzinfo=timezone.utc
    )

    while current_day < end:
        day_ts = int(current_day.timestamp())

        # Skip days already completely covered.
        expected_start = max(day_ts, start_ts)
        expected_end = min(day_ts + 86400, end_ts)

        expected_count = max(
            0,
            (expected_end - expected_start) // 60
        )

        existing_count = sum(
            expected_start <= timestamp < expected_end
            for timestamp in candles
        )

        if existing_count < expected_count:
            filename = (
                f"{symbol}-1m-"
                f"{current_day:%Y-%m-%d}.zip"
            )

            url = (
                f"{BASE_URL}/daily/klines/"
                f"{symbol}/1m/{filename}"
            )

            rows = download_zip(url)

            if rows is not None:
                added = add_rows(
                    candles, rows, start_ts, end_ts
                )

                print(
                    f"Daily {filename}: +{added}",
                    flush=True
                )

        current_day += timedelta(days=1)

    one_minute = [
        candles[key]
        for key in sorted(candles)
    ]

    if not one_minute:
        raise RuntimeError(
            f"No data collected for {symbol}"
        )

    # 3. Check missing one-minute candles.
    missing = 0

    for index in range(1, len(one_minute)):
        previous = one_minute[index - 1][0]
        current = one_minute[index][0]

        missing += max(
            0,
            (current - previous) // 60 - 1
        )

    expected_total = (end_ts - start_ts) // 60
    coverage = (
        len(one_minute) / expected_total * 100
        if expected_total else 0
    )

    print(
        f"{symbol}: {len(one_minute)} candles, "
        f"coverage={coverage:.2f}%, "
        f"internal_missing={missing}",
        flush=True
    )

    # Reject incomplete datasets.
    if coverage < 99.0:
        raise RuntimeError(
            f"{symbol}: insufficient coverage "
            f"({coverage:.2f}%)"
        )

    save_csv(symbol, 1, one_minute)

    for timeframe in [5, 15]:
        aggregated = aggregate_candles(
            one_minute, timeframe
        )

        save_csv(
            symbol, timeframe, aggregated
        )

    print(
        f"{symbol} completed!",
        flush=True
    )


def main():
    print(
        "SPACE BAR AI HISTORY V7.1",
        flush=True
    )

    now = datetime.now(timezone.utc)

    # Use completed minutes only.
    end_ts = int(now.timestamp() // 60) * 60

    end = datetime.fromtimestamp(
        end_ts, tz=timezone.utc
    )

    start = end - timedelta(
        days=DAYS_TO_COLLECT
    )

    print(
        f"Period: {start} -> {end}",
        flush=True
    )

    failures = []

    for symbol in SYMBOLS:
        try:
            collect_symbol(symbol, start, end)
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

    print(
        "\nHISTORY V7.1 COMPLETED",
        flush=True
    )


if __name__ == "__main__":
    main()
