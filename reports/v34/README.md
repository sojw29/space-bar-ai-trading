# V34 — Immutable Historical Decision Ledger

This is a local, opt-in SQLite journal of **historical BTCUSDT 5m research snapshots**, not an independent forward test or a proof of profitable trading.

## Record one observation

From the repository root, after historical data has been downloaded:

```bash
python agents/decision_ledger_v34.py --history data/history/BTC_5m.csv --db reports/v34/research_decisions.sqlite3
```

Read the most recent observations:

```bash
python agents/decision_ledger_v34.py --db reports/v34/research_decisions.sqlite3 --recent 20
```

The journal records the exact V27 event envelope and SHA-256, candle UTC timestamp, local capture timestamp and data source. Repeated identical observations are ignored. If the same candle has changed after a historical replay or strategy update, a conflict is raised rather than silently replacing the past record.

**Limitations:** The default history is delayed historical CSV, not a live price feed. Data updates are not automatically scheduled by this script. End-of-dataset strategy simulation results can shift as a dataset grows. The current ledger has no subsequent-candle outcomes, returns, accuracy score, or performance claims. Adding outcome evaluation requires an explicitly separate leakage-aware protocol. There are no accounts, keys, orders, or real trades.

**Data handling:** Store the SQLite file locally, and do not commit real run data or private logs into Git.
