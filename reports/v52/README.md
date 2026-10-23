# V52 — Verified BTCUSDT 5m market wall inside the 3D office

V52 builds a genuine **3D wall-mounted candlestick chart** in the existing Three.js research office. It draws **actual supplied, completed OHLCV observations** on an in-browser canvas texture attached to a Three.js plane. Candles are NOT randomly generated, interpolated, or claimed to be real-time without public feed connectivity.

The new read-only `GET /api/v1/market` API supplies up to 60 verified BTCUSDT 5-minute candles with explicit `source`, `realtime` and no-order flags. In historical mode, candles come from the existing local BTC 5m CSV. In explicitly opted-in public stream mode, V38 forwards its already-integrity-checked V37 completed candle buffer to the V39 memory store. Invalid OHLCV, out-of-order candles, gaps, future/unclosed bars, stale live prices, mismatched source flags, and mismatch between the wall chart's final bar and the analysis bar are rejected.

The WebGL office polls the market-board endpoint only alongside valid, read-only research events; it draws a chart when the OHLCV and current agent research timestamps match. Otherwise it displays **NO VERIFIED CHART DATA**, not a fabricated chart or an old apparently-live one. On disconnection the last directional agent research is cleared and the chart also resets.

## How to view

With a local historical CSV already present:

```bash
python agents/dashboard_api_v28.py --history data/history/BTC_5m.csv --port 8765
```

Open `http://127.0.0.1:8765/office3d` on the same computer.

For optional public read-only market transport, start the existing V39 live dashboard with `--fast-warmup` (optional) and visit the same `/office3d` route. Binance connectivity has not been independently verified in GitHub CI. V49-V51 requirements remain: browser WebGL and fetching the pinned external Three.js module from jsDelivr.

The chart deliberately excludes the forming 5-minute candle. Its timestamp is **the candle open in UTC**, and its closing price is an observation, not a guaranteed fill price. The app's decision rules are deterministic research heuristics, not trained AI with validated predictive performance.

**Safety:** no broker account, API keys, private exchange endpoints, trade execution, order submission or independently verified profit/return claims. The endpoint is localhost-only, GET-only; POST remains rejected. CI runs synthetic offline test data, static scene inspection and Node module parsing; no live exchange or visual GPU validation is claimed.
