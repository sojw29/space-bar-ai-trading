# V49 — Actual WebGL Three.js office foundation

V49 introduces a **separate actual 3D WebGL scene**, as distinct from the older CSS-based 2.5D preview.

### Open on a PC

From repository root, with a local historical CSV file available:

```bash
python agents/dashboard_api_v28.py --history data/history/BTC_5m.csv --port 8765
```

Open `http://127.0.0.1:8765/office3d` on **that same computer**, or open `/dashboard` and select **WebGL 3D 연구 사무실 열기**. For opt-in public market transport, the same route is available from the existing `agents/live_dashboard_v39.py` local server.

### Included

- A separate **Three.js v0.180.0** WebGL scene with 3D floor, grid, walls, windows, seven desks, displays and robot-like research figures. COMMANDER has a distinct central station.
- Drag/orbit and wheel zoom; click/tap a desk to select an agent, or use the keyboard-accessible agent button list.
- Polls existing read-only `GET /api/v1/agents` every 30 seconds. Colored screens show verified deterministic research decisions LONG/SHORT/WAIT. The inspector displays research reason, timestamp and risk veto status.
- Rejects unsafe flags, invalid/missing agents, vote tally mismatch, implausible live observation timestamps or disconnected/stale APIs. On failure, **clears** previously displayed agent directions and fades all displays to neutral.
- The existing fully local **2.5D dashboard is still the default**; V49 doesn't replace it. `POST` endpoints still return 405.

### Important limitations

This is *geometrically real 3D* in WebGL, but robot figures are stylized static primitives and are **not autonomous AI avatars**. It is a separate prototype scene, not a complete simulated office game.

The pinned Three.js module is fetched from an external CDN when the new page is opened. Therefore **internet access, browser WebGL compatibility and appropriate CDN availability are required**. The dashboard remains local-only, but the CDN provider can receive a normal request for the library asset. When the CDN cannot load, use the 2.5D fallback. No external market account is connected to the 3D renderer. Browser GPU performance varies; offline CI checks code contracts and syntax, not visual correctness or the CDN.

No real trading, exchange credentials, orders, broker account access, trained ML, independent verified edge or actual order fills are added.
