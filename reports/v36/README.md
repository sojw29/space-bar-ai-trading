# V36 — Offline Paper Execution Research

This is an **offline historical research simulator**, not a broker paper account, independent forward evaluation, or real trade engine. It does not submit orders, access accounts, or use API keys.

From the repository root, using a downloaded BTC 5-minute history file:

```bash
python agents/paper_execution_v36.py --history data/history/BTC_5m.csv --fee-bps 5.5 --slippage-bps 2 --notional 100 --output reports/v36/paper.json
```

The deterministic V26 COMMANDER reads candles through the last **completed** bar. When its result is LONG/SHORT (WAIT skips), a hypothetical fixed-notional position opens at the **next candle's opening** with adverse slippage, and closes at that same candle's closing with adverse slippage. Flat fee basis points are charged **on both sides**. This artificial one-candle holding window is intentional for reproducible tests; it is not a validated strategy or a recommended trading rule. Results omit order book liquidity, spread variability, funding, liquidation, queue priority, partial fills, exchange outages, mark-price differences, latency and actual brokerage fee tiers. Negative P&L is possible. No leverage or compounding is applied.

**No forward evidence:** This replays a historical data file; results are not evidence that a model will perform well in future markets. V34 and V35 retain their independent evidence limitations. No exchange account access exists.

A future true prospective paper system requires a live closed-candle feed, timestamped append-only signals, a durable order-state emulator, execution assumptions and strict reconciliation before considering any real-money integration.
