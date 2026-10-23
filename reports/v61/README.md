# V61 — Descriptive Historical Paper Performance

Adds an **explicit manual in-sample performance report** in the Windows research launcher and CLI:

```bash
python space_bar_launcher.py --paper-report data/history/BTC_5m.csv
```

The report uses **the same V60 rule-based replay** after 55 warmup candles, with at most 26 observed, completed 5-minute paper-accounting points. It records a timestamped **hypothetical mark-to-close equity curve**, computes maximum observed peak-to-trough drawdown, records closed and open *hypothetical* positions, and checks ENTRY/EXIT accounting consistency. It shows a trade count and estimated realized P&L from the existing V41 model.

**Critically: no win rate or profit factor is published from this tiny sample.** The V61 report deliberately returns `null` for these metrics until at least 30 closed positions; current replay cannot meet that threshold. A missing metric is **not 0%**. The report explicitly marks `oos_validated=false`, `independent_oos_verified=false`, `realtime=false`, and `orders_enabled=false` and rejects any contradictory source or flag.

Only existing user-provided historical OHLCV is used in normal operation. Simulated entry and exit values are based on **completed candle closes** with simplified fees/slippage and cannot represent real intrabar orders, liquidity, liquidation, funding, exchange fills, or future performance. Sample equity points are **in-sample observations**, not an independently held-out strategy test.

The GUI report is triggered separately by the user, with a background worker to avoid blocking the window. Standard V58 Windows start/stop and V59 localhost diagnostics remain. No real exchange connection, broker orders, background trading or credentials are introduced.

GitHub Actions validates deterministic output, ledger tampering, drawdown arithmetic, insufficient sample handling, CLI read-only behavior, and prior accounting regressions. Windows Tkinter visual QA remains outside Linux CI.
