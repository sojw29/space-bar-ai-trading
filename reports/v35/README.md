# V35 — Historical post-hoc outcome annotations

**Research only.** Evaluate the direction and percentage of closing-price changes *after* previously saved V34 candle decisions. Observations are labeled `HISTORICAL_POSTHOC` because historical CSVs and retrospective ledger captures do not establish an independently timestamped forward evaluation. This is **not trading P&L, an execution simulator, win rate, independent out-of-sample validation or a profitable edge**.

From repository root, after you have a V34 SQLite file and BTC 5m history:

```bash
python agents/outcomes_v35.py --db reports/v34/research_decisions.sqlite3 --history data/history/BTC_5m.csv --limit 20 --output reports/v35/outcomes.json
```

Outputs at 1, 3, and 12 subsequent **complete 5m candles**; each report has a raw closing-price percentage change and a boolean indication of whether a LONG/SHORT direction agrees with that change. WAIT has no direction-match score. Missing future candles produce a null outcome with `INSUFFICIENT_FUTURE_CANDLES`, **not a fabricated zero**. History files with any gaps or duplicates are rejected. V34 immutable ledger records are never updated.

To establish credible prospective measurements later: collect signals in real time as closed candles arrive; timestamp and hash source data at collection; pre-register outcome horizons and evaluation rules before future data arrives; separately track fees/slippage/execution and account for overlapping signals and multiple testing. Do not compare these descriptive values to backtest win rates.
