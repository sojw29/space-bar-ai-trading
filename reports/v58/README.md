# V58 — Windows double-click local research launcher

From a Windows PC with Python 3 installed (including its default **Tkinter** UI support), unzip or clone this repository and double-click `START_SPACE_BAR_WINDOWS.bat`. The batch file runs `space_bar_launcher.py` from the repository root, so relative data files resolve predictably.

The window supports **Browse** for a locally available BTC 5-minute OHLCV CSV, **Start**, **Stop**, **Open 2.5D dashboard**, and **Open 3D office**. It opens the browser only after the localhost server starts successfully. Closing the window stops that server. Port `8765` is local-only (`127.0.0.1`) and will not be force-claimed from another service. The existing `/dashboard`, `/office3d`, `/api/v1/agents` and `/api/v1/market` endpoints are reused unchanged; POST remains HTTP 405.

The CSV must already exist at `data/history/BTC_5m.csv` or be selected in the UI. It needs at least 55 well-formed, contiguous, **completed** BTC 5m candles. **No fake or generated market data is supplied for normal launcher use.** When input is absent, incomplete or invalid, the UI shows an error and refuses to start research. Do not use a file with unrelated symbols, exchanges or candle intervals. Historical source metadata is explicit, not live.

The launcher is intentionally historical-only and standard-library based. It does **not** start the optional public Binance streaming process, connect to an exchange account, take credentials, create trading orders, enable live trading or automatically install dependencies. 3D mode still needs browser WebGL and a pinned Three.js CDN download; use 2.5D mode as an offline fallback.

### Command line validation

```bash
python space_bar_launcher.py --check-history data/history/BTC_5m.csv
```

CI verifies CSV rejection, local start/stop, duplicate server/port denial, GET research views and POST 405 **without a desktop UI**. A real Windows desktop launch remains to be visually tested by a user on Windows; GitHub Actions Linux tests do not prove the Tkinter window layout works identically on Windows.

This project remains a read-only research prototype; its model performance is not independently validated.
