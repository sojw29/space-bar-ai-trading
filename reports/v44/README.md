# V44 — Paper Performance Lab (simulated-only)

V44 adds **read-only, session-scoped simulated metrics** to the SPACE BAR dashboard, backed by the opt-in V43 local SQLite paper journal.

Start from the repository root, if public feed connectivity is available:

```bash
python -m pip install websocket-client
python agents/live_dashboard_v39.py --port 8765 --fast-warmup --paper-monitor --paper-journal reports/v43/paper_journal.sqlite3
```

Open `http://127.0.0.1:8765/` **on the same computer**. The new panel requests `GET /api/v1/paper/analytics`. Without an enabled journal, it displays **미활성화**. POST is rejected; no trade controls or credentials exist.

Metrics are *descriptive observations from one simulated session*: most recently recorded paper cash and realized net, cumulative **trade event count** (entries plus exits, **not number of completed trades**), number of journal snapshots, count of halt events within the sample, and maximum peak-to-trough drawdown **only across valid recorded hypothetical equity marks**. Stale marks are excluded. With fewer than two valid marks the drawdown is **undefined**, not zero.

**Limitations**:
- To bound responses, at most the **latest 500 snapshots** are used; if the session is longer, the dashboard marks it as a partial sample. The complete hash chain is still verified before computing the metrics.
- No exchange account data, real fills, validated win rate, Sharpe, independently tested edge or prospective performance is implied. The V41 price/fee/stop model remains simplistic and may be significantly optimistic.
- Session restarts deliberately create a new paper account; previous sessions can be separately inspected offline but are not merged and never automatically resumed.
- A hash chain detects accidental corruption, not deliberate tampering or deletion by someone controlling the SQLite file.
- The implementation is a research viewer, not investment advice or an authorized auto-trader.

CI uses only simulated events/loopback HTTP, never actual Binance connectivity.
