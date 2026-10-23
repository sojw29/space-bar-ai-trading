# V43 — Opt-in append-only paper trading journal

V43 adds a local SQLite research journal to **record simulated** paper portfolio snapshots and feed halts. It does not send orders, access an exchange account, or authorize real trading. Nothing starts in the background.

## Start from repository root (desktop/PC)

```bash
python -m pip install websocket-client
python agents/live_dashboard_v39.py --port 8765 --fast-warmup --paper-monitor --paper-journal reports/v43/paper_journal.sqlite3
```

The journal is explicitly optional. The `--paper-journal` flag requires `--paper-monitor`. Public market data may be unavailable depending on connection/geography; CI tests use mocked public messages, not actual exchange traffic.

Each process launch creates a **new random session**, even if an existing journal is present. Old positions are **never automatically recovered or traded**. A session has monotonically increasing event indices, the snapshot payload, creation timestamps, and a SHA-256 hash chained to the prior row. Journaling errors halt the in-memory paper monitor rather than allow further simulated signals to go unrecorded. Database writes are transactional. Tests verify persistence across new journal instances, multi-session isolation, and corruption detection.

### Offline readback (never resumes trading)

```python
from paper_journal_v43 import verify_session, session_events
db = "reports/v43/paper_journal.sqlite3"
session_id = "copy-session-id-from-journal"
audit = verify_session(db, session_id)
events = session_events(db, session_id, limit=100)
```

See `paper_sessions` in the SQLite database to find stored session IDs.

**Integrity limitation:** A local hash chain can detect accidental row edits and interior-row deletion, but it **does not provide cryptographic authenticity against a malicious party able to rewrite the entire file or delete a suffix**. No independent external hash anchoring or identity signature is implemented. Treat it as an audit aid, not proof of independently captured live outcomes.

### Accounting and risk limitations

All holdings, fills, returns, losses and fees are simulated using V41's simplified close-price model. Intrabar execution, stop fills, funding, liquidation and exchange account reconciliation are **not** modeled. If the process stops, active paper positions do not resume. Performance is not independently verified, and the journal must **not** be mistaken for a broker statement. This version records simulated snapshots/halts; detailed reporting, trade-level attribution and visual history dashboard are later work.

Do not check in your generated SQLite journal to GitHub.
