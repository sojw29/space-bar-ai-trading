# V57 — Browser performance controls and visibility

Adds three accessible client-side WebGL quality presets: **low (DPR cap 1)**, **balanced (DPR cap 1.5)** and **high (DPR cap 2)**. These alter only the rendered pixel density, not the market feed, signals, paper positions, or research data. The panel reports output pixel dimensions, approximate on-screen frames per second (measured from browser render iterations), and whether rendering is active, paused, or failed. Frame counts reset on suspension, not displayed as guaranteed GPU benchmarks.

The existing read-only localhost 3D page remains at `http://127.0.0.1:8765/office3d` with the 2.5D fallback at `/dashboard`. Older completed BTCUSDT candles, COMMANDER consensus and local feed safety checks are unchanged. No brokerage credentials or order functions are included.

### Browser regression

GitHub Actions now exercises a **1.5x device-pixel-ratio** software-WebGL Chromium viewport and checks that the low and high quality controls work and update render resolution. It still tests the real rendered 3D scene, API disconnection fail-closed path, Three.js module-load fallback and POST 405. The Chromium test uses generated historical sample data and a locally intercepted pinned Three.js module, *not* Binance connectivity. Screenshots are uploaded from the V57 artifact directory.

**Limitations**: estimated FPS observed inside a software-rendered browser is not a comparable FPS benchmark on a user's hardware, and image screenshots do not guarantee acceptable appearance on every device. No real-money orders, independent out-of-sample returns or live-trading claims.
