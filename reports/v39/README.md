# V39 — Local public stream → read-only dashboard

V39 connects the V38 **public Binance BTCUSDT USD-M Futures WebSocket market-data adapter** to a **localhost-only** dashboard and V26/V27 multi-agent research events. No keys, account endpoints, real-money execution, exchange orders, or paper-broker orders are present.

## Optional local start

From repository root:

```bash
python -m pip install websocket-client
python agents/live_dashboard_v39.py --port 8765
```

Then open **http://127.0.0.1:8765/** on the **same computer**. No server starts automatically, and the GitHub CI suite uses mocked data rather than a real Binance connection.

The process starts one read-only WebSocket worker and one loopback HTTP server; the bridge passes results through a lock-protected in-memory store. Routes:
- `GET /api/v1/feed`: connection/warmup/failure/stale status (never exposes order controls).
- `GET /api/v1/agents`: a V27 envelope and `realtime:true` only after 55 consecutive valid **completed 5-minute** bars. Returns HTTP **503** during warmup, disconnection and stale state.
- `GET /dashboard` or `/`: room/inspector/consensus display; polls every 30 seconds. Connection problems clear prior displayed trading directions.
- `POST`: rejected as read-only.

**First research signal takes at least 4h 35m of uninterrupted final candles** because the V38 adapter intentionally does not backfill. A gap or reconnection invalidates the prior buffer and restarts warm-up. Disconnects and stale data invalidate previously published research output. Events are not stored persistently and will vanish on restart. This is a **live transport**, not evidence of real-time trading performance or a production-grade execution system.

V39 enforces both receipt-age and the final candle's UTC age. It does not independently verify exchange availability, clock accuracy, endpoint geography/legal availability, funding, live fills or slippage. Current agent decisions are deterministic research heuristics, and independent out-of-sample results remain unverified. Never publish the unauthenticated localhost service to the Internet.
