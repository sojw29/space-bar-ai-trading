"""V37 completed-candle stream gate: transport-neutral, paper-only.

Consumes OHLCV dicts explicitly marked closed from a future data adapter.
Rejects incomplete, future, duplicate, out-of-order and gapped bars.
No network access, broker integration, or order execution. Warm-up requires
55 contiguous completed 5-minute candles before emitting V27 research events.
"""
from collections import deque
from datetime import datetime, timezone
import math

import agent_events_v27 as events
import multi_agent_v26 as agents

PERIOD_SECONDS = 300
MIN_BARS = 55
MAX_BARS = 120


class StreamIntegrityError(ValueError):
    """Unsafe input prevents a research event."""


class ClosedCandleStream:
    def __init__(self, *, now=None):
        self._now = now or (lambda: datetime.now(timezone.utc).timestamp())
        self._candles = deque(maxlen=MAX_BARS)
        self._last_ts = None
        self._resets = 0
        self._emissions = 0

    @property
    def status(self):
        return {
            "mode": "completed_candle_research",
            "realtime_feed_connected": False,
            "buffered_bars": len(self._candles),
            "last_timestamp": self._last_ts,
            "gap_resets": self._resets,
            "emissions": self._emissions,
            "paper_only": True,
            "orders_enabled": False,
        }

    def recent_closed_candles(self, limit=60):
        """Immutable-by-copy completed candle observations for read-only UI."""
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=80:
            raise ValueError("Invalid market-board limit")
        return [dict(row) for row in list(self._candles)[-limit:]]

    def ingest(self, candle):
        """Return a V27 envelope after warm-up; otherwise None.

        Expected shape:
          {timestamp: int UTC candle-open epoch seconds, open, high, low,
           close, volume: numbers, closed: True}.
        External transport must independently verify candle finality.
        """
        if not isinstance(candle, dict) or candle.get("closed") is not True:
            raise StreamIntegrityError("Only explicitly completed candles accepted")
        ts = candle.get("timestamp")
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            raise StreamIntegrityError("Invalid candle timestamp")
        if ts % PERIOD_SECONDS != 0:
            raise StreamIntegrityError("Timestamp not aligned to 5m boundary")
        try:
            o,h,l,c,v = (agents._safe_number(candle[k], k) for k in
                         ("open","high","low","close","volume"))
        except (KeyError, ValueError) as error:
            raise StreamIntegrityError("Invalid OHLCV value") from error
        if min(o,h,l,c)<=0 or h<max(o,c) or l>min(o,c) or v<0:
            raise StreamIntegrityError("Invalid OHLCV relationships")
        current = float(self._now())
        if not math.isfinite(current) or ts + PERIOD_SECONDS > current:
            raise StreamIntegrityError("Candle not complete according to local clock")
        if self._last_ts is not None:
            if ts <= self._last_ts:
                raise StreamIntegrityError("Duplicate or out-of-order candle")
            if ts != self._last_ts + PERIOD_SECONDS:
                self._candles.clear()
                self._resets += 1
                # A gap invalidates prior signals. The caller must surface
                # the reset and avoid treating previous results as current.
        clean = {"timestamp": ts,"open": o,"high": h,"low": l,"close": c,"volume": v}
        self._candles.append(clean)
        self._last_ts = ts
        if len(self._candles) < MIN_BARS:
            return None
        report = events.analyze_and_emit(list(self._candles))
        self._emissions += 1
        return report


def replay_closed_history(rows, *, now=None):
    """Convenience offline demonstration; not a connected realtime feed."""
    stream = ClosedCandleStream(now=now)
    output = []
    for row in rows:
        event = stream.ingest({**row, "closed": True})
        if event is not None:
            output.append(event)
    return output, stream.status
