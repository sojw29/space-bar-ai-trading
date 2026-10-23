# V40 — Optional public REST warm-up (no orders)

V40 adds **opt-in fast warmup** of the read-only BTCUSDT 5-minute research dashboard, using Binance USD-M **public** `GET /fapi/v1/klines` REST candles and then the existing public WebSocket.

From the repository root, after installing the optional public WebSocket dependency:

```bash
python -m pip install websocket-client
python agents/live_dashboard_v39.py --port 8765 --fast-warmup
```

Open `http://127.0.0.1:8765/` **on that same computer**.

Without `--fast-warmup`, the V39 behavior remains unchanged: at least 55 consecutive completed 5-minute candles must arrive on the WebSocket. With the opt-in flag, the newly connected WebSocket remains open while the **public REST** request fetches 55–65 recent BTC 5m candles. The warmup code rejects missing/duplicated/out-of-order candles, malformed OHLCV, malformed timestamps and future/unclosed candles, and rejects REST history if the most recent completed candle is more than 420 seconds old. It primes the V37 research buffer only if these checks pass.

The next **completed WS candle** must continue the REST series exactly. A repeated last closed candle is skipped only if OHLCV agrees to tight numeric tolerance; older or inconsistent WS messages fail closed and trigger a fresh connection/revalidation. A feed disconnect, an invalid REST fetch, gap, or stale data clears published decisions. REST preload itself does **not** publish trading signals: a verified subsequent WS close is needed.

**Limitations**: This is **public price-data infrastructure**, not an execution or real-time portfolio system. Exchange market feed/REST connectivity, geographic availability and clock synchronization must be verified in your local environment. Server remains bound to `127.0.0.1`; do not expose it publicly. No API keys, private endpoints, exchange accounts, trades or orders. Agents are heuristic research only and have no validated independent live edge.

Binance official REST reference: https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data
