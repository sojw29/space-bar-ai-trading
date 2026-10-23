# V55 — WebGL fallback and runtime recovery

V55 makes the read-only 3D research office more resilient to missing WebGL capabilities, blocked CDN/module downloads and temporary browser graphics-context losses.

The new **classic-script startup watchdog** runs independently of the externally loaded Three.js ES module. If WebGL is missing, initialization fails, or the external module does not render within 15 seconds, the page shows an accessible **2.5D dashboard fallback link** instead of displaying an indefinite spinner. This is a user-visible fallback, not a secondary fake 3D renderer.

The actual renderer listens for browser `webglcontextlost` and `webglcontextrestored` events. On context loss it pauses animation and clears research/market/consensus state. A restored context requests fresh data before drawing research. Switching to another browser tab pauses rendering and, on return, revalidates research state rather than presenting stale decisions. Existing 30-second research polling, 5-second freshness watchdog, and opt-in read-only market mode remain.

The local server continues to serve `http://127.0.0.1:8765/office3d` and `/dashboard` without supporting POST/orders. Three.js is pinned to an external CDN URL; the fallback handles loader failure, but the full 3D scene still requires WebGL and network access.

CI tests parse the independent classic JavaScript and Three.js module, verify fallback/recovery hooks and read-only HTTP routes, and run prior 3D and API contracts. **CI is not a real-browser GPU/visual test and does not claim the WebGL context was manually exercised.** No exchange credentials, account balances, actual trades, model training or independently verified returns are introduced.
