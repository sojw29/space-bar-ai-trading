# ============================================================
# SPACE BAR AI TRADING
# HISTORY V6.1 - BINANCE PUBLIC MARKET DATA
# PAPER RESEARCH ONLY
# ============================================================

import csv
import json
import os
import time

from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
TIMEFRAMES = [1, 5, 15]

DATA_DIR = "data/history"

API_URLS = [
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
]

TARGET_1M_CANDLES = 10000
LIMIT = 1000
MAX_RETRIES = 3

os.makedirs(DATA_DIR, exist_ok=True)


def request_klines(symbol, end_ms):

    params = (
        f"?symbol={symbol}"
        f"&interval=1m"
        f"&limit={LIMIT}"
        f"&endTime={end_ms}"
    )

    last_error = None

    for base_url in API_URLS:

        url = base_url + params

        for attempt in range(MAX_RETRIES):

            try:

                request = Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "application/json",
                    },
                )

                with urlopen(request, timeout=30) as response:
                    data = json.loads(
                        response.read().decode("utf-8")
                    )

                if not isinstance(data, list):
                    raise RuntimeError(
                        f"Unexpected response: {data}"
                    )

                return data

            except (
                HTTPError,
                URLError,
                TimeoutError,
                ValueError,
                RuntimeError,
            ) as error:

                last_error = error

                print(
                    f"API retry {attempt + 1}/{MAX_RETRIES}: "
                    f"{error}",
                    flush=True,
                )

                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)

    raise RuntimeError(
        f"Failed to download {symbol}: {last_error}"
    )


def validate_candle(candle):

    timestamp, op, hi, lo, cl, vol = candle

    if min(op, hi, lo, cl) <= 0:
        return False

    if vol < 0:
        return False

    if hi < max(op, cl):
        return False

    if lo > min(op, cl):
        return False

    if timestamp % 60 != 0:
        return False

    return True


def save_csv(symbol, timeframe, candles):

    short_symbol = symbol.replace("USDT", "")

    path = (
        f"{DATA_DIR}/"
        f"{short_symbol}_{timeframe}m.csv"
    )

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ])

        writer.writerows(candles)

    print(
        f"Saved {path}: {len(candles)} candles",
        flush=True,
    )


def aggregate_candles(one_minute, timeframe):

    result = {}

    seconds = timeframe * 60

    for candle in one_minute:

        timestamp, op, hi, lo, cl, vol = candle

        bucket = (timestamp // seconds) * seconds

        if bucket not in result:

            result[bucket] = [
                bucket,
                op,
                hi,
                lo,
                cl,
                vol,
                1,
            ]

        else:

            item = result[bucket]

            item[2] = max(item[2], hi)
            item[3] = min(item[3], lo)
            item[4] = cl
            item[5] += vol
            item[6] += 1

    # Incomplete 5m/15m candles are excluded.
    candles = []

    for bucket in sorted(result):

        item = result[bucket]

        if item[6] == timeframe:
            candles.append(item[:6])

    return candles


def collect_symbol(symbol):

    print(
        f"\nCollecting {symbol}",
        flush=True,
    )

    candles = {}

    now = datetime.now(timezone.utc)

    current_minute = (
        int(now.timestamp()) // 60
    ) * 60

    end_ms = current_minute * 1000 - 1

    max_requests = 20

    for request_number in range(max_requests):

        batch = request_klines(
            symbol,
            end_ms,
        )

        if not batch:
            break

        oldest_ms = None

        for item in batch:

            timestamp_ms = int(item[0])
            timestamp = timestamp_ms // 1000

            if (
                oldest_ms is None
                or timestamp_ms < oldest_ms
            ):
                oldest_ms = timestamp_ms

            if timestamp >= current_minute:
                continue

            candle = [
                timestamp,
                float(item[1]),
                float(item[2]),
                float(item[3]),
                float(item[4]),
                float(item[5]),
            ]

            if validate_candle(candle):
                candles[timestamp] = candle

        print(
            f"{symbol}: request {request_number + 1}, "
            f"total={len(candles)}",
            flush=True,
        )

        if len(candles) >= TARGET_1M_CANDLES:
            break

        if oldest_ms is None:
            break

        end_ms = oldest_ms - 1

        time.sleep(0.3)

    one_minute = [
        candles[key]
        for key in sorted(candles)
    ]

    one_minute = one_minute[-TARGET_1M_CANDLES:]

    if len(one_minute) < TARGET_1M_CANDLES:

        raise RuntimeError(
            f"{symbol}: insufficient data "
            f"({len(one_minute)}/"
            f"{TARGET_1M_CANDLES})"
        )

    # Require consecutive 1-minute candles.
    for index in range(1, len(one_minute)):

        previous = one_minute[index - 1][0]
        current = one_minute[index][0]

        if current - previous != 60:

            raise RuntimeError(
                f"{symbol}: missing 1m candles "
                f"between {previous} and {current}"
            )

    save_csv(
        symbol,
        1,
        one_minute,
    )

    for timeframe in [5, 15]:

        aggregated = aggregate_candles(
            one_minute,
            timeframe,
        )

        if not aggregated:
            raise RuntimeError(
                f"{symbol}: no {timeframe}m data"
            )

        save_csv(
            symbol,
            timeframe,
            aggregated,
        )

    print(
        f"{symbol} completed!",
        flush=True,
    )


def main():

    print(
        "SPACE BAR AI HISTORY V6.1",
        flush=True,
    )

    failures = []

    for symbol in SYMBOLS:

        try:
            collect_symbol(symbol)

        except Exception as error:

            print(
                f"ERROR {symbol}: {error}",
                flush=True,
            )

            failures.append(symbol)

    if failures:

        raise RuntimeError(
            "History collection failed: "
            + ", ".join(failures)
        )

    print(
        "\nAll market history collected!",
        flush=True,
    )


if __name__ == "__main__":
    main()
