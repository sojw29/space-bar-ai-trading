# V62 — Chronological descriptive paper holdout (not independent proof)

V62 creates a **70% development / 30% later holdout** research report from 200–5000 contiguous **completed BTCUSDT 5-minute OHLCV candles**, taken directly from a user-provided historical CSV. It uses the **existing fixed V26/V27 rules** without model training, parameter fitting or optimization. The two segments use **separate hypothetical paper portfolios**, initial paper capital of 10,000 each, and 55 bars of exclusively past feature warmup. The holdout portfolio never inherits a development position or realized P&L. Features at each bar may use **past** bars from before the holdout boundary (normal causal lookback), but no future prices.

The report includes UTC evaluation boundaries and counts, hypothetical equity curves, observed drawdown, hypothetical open positions, closed-trade counts, and paper cash/realized estimates from existing V41 close-price accounting. Win rate and profit factor are suppressed unless **at least 30 closed simulated trades** occur in a segment. No missing data, invalid OHLCV, unclosed/future candles or more than 5,000 rows are silently accepted. No market data is fabricated in normal operation.

Use Windows launcher **Evaluate chronological holdout (manual)** after starting the local historical research server, or CLI without the GUI/server:

```bash
python space_bar_launcher.py --holdout-report data/history/BTC_5m.csv
```

**This is a descriptive chronological split, not independent out-of-sample validation**: the V26 rules have been iteratively developed and observed historically, and a single holdout partition can be overfit by future choices. V62 marks `oos_validated=false`, `independent_oos_verified=false`, `model_fitting_performed=false`, `paper_only=true`, `orders_enabled=false`, and `realtime=false`. No predictive edge, trade execution, broker access, exchange account connectivity, actual fills or simulated stop precision is claimed. True prospective validation requires pre-registered frozen rules and new unseen observations.

GitHub CI tests chronological separation, historical integrity, insufficient samples and no-order CLI behavior with **synthetic offline test fixtures**; no live exchange connection or Windows GUI appearance is tested.
