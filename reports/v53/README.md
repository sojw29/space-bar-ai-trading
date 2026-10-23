# V53 — 3D COMMANDER Consensus Control Room

V53 adds a separate 3D wall screen for COMMANDER's confirmed research consensus and a read-only accessible HTML panel for six deterministic role votes (ATLAS, ORBIT, ECHO, PULSE, QUANT and APEX). Each agent's current vote is mirrored by a colored 3D line pointing to the COMMANDER desk, while the wall shows LONG/SHORT/WAIT counts and the APEX-related risk-veto state.

This information is **not invented from animation or random numbers**. It comes only from the validated V27 research envelope returned by the existing same-origin, localhost-only `GET /api/v1/agents` endpoint. V53 repeats the vote tally and deterministic COMMANDER-decision check before painting 3D elements. If the feed is unavailable, stale, malformed, or fails validation, the wall and six visual links reset to an explicit offline/unverified state and all previous research decisions are cleared.

No independent market prediction model, live order or real trading action is added. The agents remain fixed research heuristics and the WebGL room does not represent actual autonomous AI collaboration.

From a local computer, run the existing V28 historical research server or opt-in V39 public-market research server and open `http://127.0.0.1:8765/office3d`. Like prior versions, the scene needs a browser that supports WebGL and a connection to the pinned Three.js CDN. The default 2.5D dashboard remains under `/dashboard`.

CI verifies JavaScript module syntax, offline research contract regression, UI safety and GET-only localhost routing. **It does not validate actual browser/GPU appearance or a real exchange connection.** Any real-money execution remains disabled.
