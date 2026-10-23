# V54 — 3D Operations & Connection Status (local, read-only)

V54 adds an operations panel within the existing `/office3d` Three.js research scene. It shows the **browser's local time**, the most recent local API check, current `/api/v1/feed` transport state, validation of `/api/v1/agents` research events, and the age of the last completed 5-minute BTCUSDT observation.

The panel distinguishes **HISTORICAL** CSV data from explicitly opted-in public-market research transport. It never interprets a working WebGL scene as evidence of a live exchange connection, and it does **not** describe an exchange account connection. Both API endpoints are same-origin GET-only and local server still binds `127.0.0.1`.

The UI cross-checks `/api/v1/feed` source mode and readiness against the research event's `realtime` flag. When the feed is disconnected, warming up, incomplete, inconsistent, or unavailable, previously shown agent votes, directions and both 3D market/consensus wall views are **reset**. A lightweight 5-second clock refresh additionally clears previously visible public-stream research when its open-time age exceeds 12 minutes, even if the browser's next 30-second API poll has not yet run. Historical data is explicitly labelled **not realtime**; an old historical timestamp is not a public feed outage.

No orders, broker APIs, credentials, persistent background monitor or live trading are added.

## View

Start the existing localhost research server with a valid local BTC 5-minute CSV or opt in to the existing V39 public feed, then open `http://127.0.0.1:8765/office3d` on the **same computer**. Opening the 3D page requires a WebGL browser and an external pinned Three.js CDN download. The 2.5D fallback is `/dashboard`.

Offline GitHub Actions verify the JavaScript module syntax, previous research and scene contracts, no-order HTTP behavior, and V54 operations display. **CI does not verify actual browser GPU appearance or real Binance market connectivity.**

Potential operational limitations: the browser clock may be misconfigured; HTTP polling every 30 seconds and local clock freshness checks are not an independent telemetry/uptime system. The V26 research heuristics and hypothetical paper accounting remain unverified for real profits.
