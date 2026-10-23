# V59 — Local launcher diagnostics and event history

V59 adds a **local-only diagnostic panel** to the V58 Python/Tkinter Windows launcher.

- Once the historical research server is started, a **single background worker** periodically queries only `127.0.0.1` read-only GET endpoints: `/health`, `/api/v1/feed`, `/api/v1/agents`, and `/api/v1/market`. It rejects unsafe order flags, unexpected live-feed mode and mismatched historical provenance.
- A bounded in-memory event list (50 entries max) shows lifecycle and health transitions. Only a fixed whitelist of event descriptions is allowed, to avoid recording file paths, tokens or raw errors. No log is written to disk.
- The GUI distinguishes verified historical research from unavailable research, with **paper simulation explicitly not enabled**. It does not imply an exchange account is connected.
- The background worker avoids blocking the Tkinter event loop on HTTP requests. Stopping the launcher closes only its own local server.
- The V58 project root resolution is fixed for correct double-click launching when launched from the repository root.

This does **not** automatically start Binance WebSocket/public live transport, paper trading, external services, private APIs or broker order placement. Actual trading remains disabled.

### Run

From the project folder on Windows, double-click `START_SPACE_BAR_WINDOWS.bat` (requires Python 3 with Tkinter installed). Choose an existing valid BTC 5-minute historical CSV, then click **Start local research**. The 3D view requires WebGL and the external pinned Three.js CDN.

Offline CI tests HTTP lifecycle and diagnostics, closed-on-failure source mode checks, bounded redaction and POST denial. **Actual Windows Tkinter visual testing is still outstanding.** Analysis results are deterministic research rules without independently verified investment returns.
