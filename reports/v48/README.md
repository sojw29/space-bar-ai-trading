# V48 — Observable Office Activity

V48 adds **evidence-based UI refresh phases** to the local 2.5D CSS office.
These describe the read-only browser request/response lifecycle, **not** an
agent independently thinking, working in the background or executing trades.

- **FETCHING** — local browser is waiting for the `/api/v1/agents` response.
- **OBSERVED** — a well-formed V27 completed-candle research response was accepted.
- **WAITING** — the last accepted research snapshot is visible; next check
  occurs on the existing 30-second polling interval.
- **BLOCKED** — research response is absent, malformed or stale, or the feed
  is disconnected. Prior directional room indications and inspector evidence
  are cleared to WAIT/unavailable.

When `realtime:true`, V48 additionally checks local browser-clock age:
a closed candle older than approximately 12 minutes (from candle-open UTC)
is considered stale and is **not** displayed as current research.
Local machine time must be correct. Historical CSV snapshots do not have
this freshness requirement; the UI continues to label them historical.

Each desk displays a small phase indicator and retains its independently
received LONG/SHORT/WAIT decision status. APEX veto indicators and the
COMMANDER consensus remain research-only and **never** mean authorization to
place orders. Reduced-motion accessibility and mobile layouts are retained.

No Three.js/WebGL scene, real 3D characters, autonomous agent workflows,
real market orders, API keys, exchange accounts, or validated trading edge
are introduced in this version. Tests check static interface contracts and
Node.js JavaScript syntax offline; browser visual QA is still recommended.
