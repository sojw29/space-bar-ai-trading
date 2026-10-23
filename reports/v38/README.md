# V38 — Opt-in public Binance USD-M WebSocket adapter

V38 can **receive public BTCUSDT 5m kline data** from Binance USD-M Futures when explicitly started locally. It uses Binance's updated **market** WebSocket endpoint (the former legacy root endpoint was retired in April 2026). Public market feeds do not require credentials. **No private/account endpoints, exchange keys, orders, positions or real money.**

## Optional local run

From repository root:

```bash
python -m pip install websocket-client
python agents/binance_public_ws_v38.py --max-attempts 3
```

Leave off `--max-attempts` to allow reconnect attempts until the process is stopped. This script **does not start itself**, and GitHub Actions tests use injected mock sockets only (no Binance network access).

JSON Lines are printed to standard output:
- `feed_status: CONNECTING / WARMING_UP / DISCONNECTED / GAP_RESET / INVALID_CANDLE_RESET`
- `research_events`: once **55 consecutive verified closed 5-minute candles** arrive, a V27 research envelope is emitted for each subsequent completed candle.

A clean WebSocket reconnection intentionally discards the old rolling buffer and requires a fresh 55-bar warm-up (at least 4 hours 35 minutes without backfill), so no prior signal is silently reused. Missing closed candles reset warm-up; unexpected metadata, duplicates and out-of-order arrivals fail closed. The producer verifies exchange `k.x == true` and the 5-minute close-time metadata; V37 independently checks local-clock finality.

**Caveats:** WebSocket **transport may be live**, but analyses have not been validated as profitable, and no live dashboard transport has been wired to this JSONL stream yet. A real deployment must add clock-skew validation, authenticated/reliable transport monitoring, reconnect/backfill, durable append-only event capture, bounded queue/backpressure, health metrics, error logging and independent forward performance evaluation. Coverage can vary by location and exchange rules. Never treat emitted research signals as order instructions.

Binance market feed reference: https://developers.binance.info/docs/derivatives/usds-margined-futures/websocket-market-streams/All-Market-Mini-Tickers-Stream
