# V56 — Real-browser 3D smoke and visual artifacts

V56 takes the existing **actual Three.js WebGL** SPACE BAR research office through a real headless Chromium browser rather than relying only on static HTML and Node syntax tests.

### What is now tested

- Launches the **production localhost Python V28 research HTTP server** on `127.0.0.1` and supplies 80 synthetic, contiguous and explicitly historical BTCUSDT 5-minute OHLCV candles. No public Binance, order API, exchange account, API keys or real-market data is used.
- Runs Chromium using software WebGL and bundles exactly the pinned Three.js `0.180.0` module **inside the CI runner** using esbuild. The browser request for the public CDN path is intercepted and served with the local compiled module, which avoids a live CDN dependency in the test. Normal users still load the standard CDN module.
- Waits for the actual WebGL renderer to reach ready, verifies its canvas dimensions, checks the completed-candle 3D market wall and operating panels, uses the COMMANDER camera view and clicks the ATLAS agent selector.
- Simulates a disconnected research API (HTTP 503) to check that last consensus, price wall and directional evidence are cleared.
- Simulates a missing Three.js module to ensure the classic-script watchdog offers the **2.5D dashboard fallback**.
- Verifies HTTP POST still returns 405.
- Saves real Chromium **screenshots** of normal, disconnected and failed-module displays as workflow artifacts, including if a later step fails.

### Running on a PC

Run these commands from `web/e2e` with Node.js 22, npm and Python 3 available:

```bash
npm install
npx playwright install chromium
npm test
```

The test starts/stops its own temporary local research server. It requires internet only for the initial npm/browser package installation; no exchange connectivity is used during the test. Generated screenshots are saved to `reports/v56/browser-artifacts/` by default and **must not be treated as independently verified trading evidence**. The dashboard itself remains a read-only local research UI.

### Limitations

Chromium software WebGL isn't representative of every user's GPU, mobile browser, driver or Three.js CDN availability. Automated screenshots and assertions establish the tested browser behaviors, not perfect visual quality. The tested BTC history is synthetic, not actual Binance ticks. All agent signals remain deterministic research heuristics and no independently tested strategy returns, broker fills, keys, orders or live trading features are enabled.
