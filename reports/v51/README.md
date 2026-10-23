# V51 — Distinct 3D Agent Characters

V51 builds on the separate Three.js WebGL office by giving each of the seven
**rule-based research roles** a distinguishable model color and static 3D
insignia. ATLAS, ORBIT, ECHO, PULSE, QUANT, APEX and COMMANDER use different
geometry (crest, ring, antenna, pulse icon, cube, shield and crown).

An inspector field displays whether there is a **validated completed-candle
research result** for the selected agent. The status and the model's modest
head pose derive only from confirmed LONG/SHORT/WAIT research events. A
missing/disconnected/stale feed returns all figures to a neutral offline
display. Nothing implies the agents are autonomously working, thinking,
talking, or physically operating a trading terminal.

The full office remains available at
`http://127.0.0.1:8765/office3d` from the existing local server. The
2.5D fallback remains `/dashboard`. The pinned Three.js module must be
loaded from an external CDN and WebGL support is required.

This is display-only geometry and UI interaction: no model training, validated
strategy edge, executable trading signal, broker connectivity, account API
keys, order placement or real-money transactions. Offline CI validates syntax
and read-only UI contracts, **not** actual browser/GPU rendering or real
Binance exchange connectivity.
