# SPACE BAR AI TRADING

A local-first, read-only multi-agent crypto market **research prototype** with historical BTC 5-minute candles, a browser dashboard, and an optional Three.js 3D research office. **Not a live trading bot**: no broker orders, private exchange accounts, or demonstrated investment returns.

## Easy start on Windows (V58)

1. Install Python 3 with Tkinter support, then obtain this repository on your computer.
2. Make sure you have a **real** BTC 5-minute CSV with `timestamp,open,high,low,close,volume` columns and at least 55 contiguous, completed candles. Default path: `data/history/BTC_5m.csv`.
3. Double-click **`START_SPACE_BAR_WINDOWS.bat`**.
4. Choose the CSV using **Browse** (if necessary), then press **Start local research**.
5. Open **2.5D dashboard** or **3D office**. Use **Stop** or close the launcher window to stop the localhost server.

The server binds **only to `127.0.0.1:8765`**. A missing/invalid CSV or occupied port is reported rather than substituted with invented data. The 3D page requires WebGL and network access for a Three.js CDN asset; the 2.5D page is the fallback.

Alternative CLI: `python agents/dashboard_api_v28.py --history data/history/BTC_5m.csv --port 8765` (runs until Ctrl+C). For additional features or developer test workflows, see `reports/`.

**Research-only safety:** GET endpoints return historical analysis or explicitly opted-in public market observations; POST returns HTTP 405. V58's desktop launcher starts historical read-only mode only. No exchange API keys, account connectivity or real trades.
