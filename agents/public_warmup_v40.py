"""V40 opt-in public REST warmup for read-only BTCUSDT 5m research.

Loads closed candles from public Binance USD-M Futures REST, with strict
continuity/finality/freshness checks, before consuming the already-connected
V38 WebSocket. No keys, account endpoints, orders or real trading.
"""
import json
import math
import time
from urllib.request import Request, urlopen

from closed_candle_stream_v37 import ClosedCandleStream

PUBLIC_REST_URL = "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=5m&limit=65"
INTERVAL_MS = 300000
MIN_BARS = 55
MAX_LAG_SECONDS = 420
MAX_RESPONSE_BYTES = 131072


def fetch_public_klines(*, fetch=None):
    """No network call occurs until explicitly invoked."""
    if fetch is None:
        def fetch():
            request = Request(PUBLIC_REST_URL, headers={"User-Agent": "SpaceBar-Research/40"})
            with urlopen(request, timeout=10) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("Kline REST response too large")
            return json.loads(raw)
    return fetch()


def parse_warmup(raw, *, now=None):
    now = float(time.time() if now is None else now)
    if not math.isfinite(now):
        raise ValueError("Invalid clock")
    if not isinstance(raw, list) or not MIN_BARS <= len(raw) <= 65:
        raise ValueError("REST payload must contain 55..65 klines")
    closed = []
    previous = None
    for row in raw:
        if not isinstance(row, list) or len(row) < 7:
            raise ValueError("Malformed kline row")
        opened, ended = row[0], row[6]
        if (isinstance(opened, bool) or not isinstance(opened, int) or
            isinstance(ended, bool) or not isinstance(ended, int) or
            opened < 0 or opened % INTERVAL_MS or ended != opened + INTERVAL_MS - 1):
            raise ValueError("Invalid kline timestamps")
        if previous is not None and opened != previous + INTERVAL_MS:
            raise ValueError("Missing, duplicate or out-of-order REST kline")
        previous = opened
        if ended / 1000 + 0.001 > now:
            # REST may include one currently-forming last candle, but not
            # any subsequent candle or non-final row in the middle.
            if row is not raw[-1]:
                raise ValueError("Unclosed candle inside warmup history")
            continue
        candle = {
            "timestamp": opened // 1000,
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
            "closed": True,
        }
        # Reuse strict V37 OHLCV checks in the actual preload function.
        closed.append(candle)
    if len(closed) < MIN_BARS:
        raise ValueError("Too few completed candles for warmup")
    if not 0 <= now - (closed[-1]["timestamp"] + 300) <= MAX_LAG_SECONDS:
        raise ValueError("Warmup snapshot stale or from future")
    return closed


def bootstrap_stream(stream, *, fetch=None, now=None):
    """Prime a fresh V37 buffer; return last completed kline for overlap checks.

    The caller must call this once *after* a new socket is connected and
    before consuming messages, and must discard buffer on any exception.
    The only emitted decisions come from later completed WS events.
    """
    rows = parse_warmup(fetch_public_klines(fetch=fetch), now=now)
    for row in rows:
        stream.ingest(row)
    if stream.status["buffered_bars"] < MIN_BARS:
        raise ValueError("V37 buffer not warmed")
    return rows[-1]


def compare_overlap(candle, previous):
    """Only an identical last REST candle may be skipped as a WS overlap."""
    if candle["timestamp"] != previous["timestamp"]:
        return False
    return all(math.isclose(float(candle[field]), float(previous[field]),
                            rel_tol=1e-10, abs_tol=1e-9)
               for field in ("open", "high", "low", "close", "volume"))
