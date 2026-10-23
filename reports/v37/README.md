# V37 — Completed 5m candle stream integrity gate

V37 provides an **in-memory, offline/transport-neutral input buffer** for a future exchange market-data feed. No exchange WebSocket, REST polling, account connection or live trading is enabled by this change.

Each incoming BTC 5m OHLCV dictionary must have `closed: True` and a UTC epoch-second opening timestamp aligned to 5 minutes. The gate rejects invalid candle shapes, incomplete/future bars (according to the injected/local clock), duplicates and out-of-order delivery. A missing 5-minute bar clears the rolling history and requires **55 new contiguous closed bars** before emitting any new research signal. The caller must also clear previously displayed signals after a gap.

After warm-up, the gate passes the last 55–120 closed bars through the existing V26 rules and emits the V27 research-event JSON for the UI. It contains no price prediction model, broker or paper execution path.

Use in another Python module:

```python
from closed_candle_stream_v37 import ClosedCandleStream
stream = ClosedCandleStream()
envelope = stream.ingest({
    "timestamp": 1700000100, "open": 100, "high": 102,
    "low": 99, "close": 101, "volume": 120,
    "closed": True,
})
# envelope is None until 55 contiguous completed bars arrive.
```

The demonstration timestamp is historical. Future integrations must **independently validate exchange completion events and UTC clock skew**, handle replay/backfill and reconnects, define stale-data policy, and distinguish immutable forward capture from replayed history. Local process restarts lose this in-memory buffer. This code has no independently verified out-of-sample edge, cannot place orders, and should not be used for live trading.
