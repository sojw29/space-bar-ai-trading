# V60 — Manual offline hypothetical paper control

The Windows localhost desktop launcher gains a **manually triggered historical paper replay**. When the user explicitly presses **Run historical paper replay (manual)**, a background worker validates up to the last 80 supplied **completed, contiguous** BTCUSDT 5-minute candles; uses the existing deterministic V27 agent decision contract; warms up for 55 bars; and feeds each subsequent closed candle into the existing V41 **hypothetical** paper accounting model.

The GUI displays marked-to-close simulated equity, simulated cash, estimated realized P&L, hypothetical position direction and entry/exit event counts. Replay results are calculated from **past data already known to the program**, not a future out-of-sample forecast. The replay starts fresh on each click and **never** starts automatically or leaves a simulated account running in the background. The default desktop launcher remains read-only historical CSV mode. No exchange account, live feed, API keys, broker orders or real-money transfers are possible through V60.

The V41 accounting engine assumes hypothetical entry and exit at completed candle closes, with a simplified slippage/fee model and close-observed stop/take thresholds. It does **not** model intrabar executions, order book, liquidation, funding, market impact, network delays, or actual available fills. Its result is **not** independently verified profitability.

## How to use

From the repository root on a Windows PC with Python 3 and Tkinter installed, double-click `START_SPACE_BAR_WINDOWS.bat`. Choose a real BTC 5-minute historical CSV, click **Start local research**, then **Run historical paper replay (manual)**. For CLI-only replay:

```bash
python space_bar_launcher.py --paper-replay data/history/BTC_5m.csv
```

The CLI prints an explicit JSON record marked `EXPLICIT_HISTORICAL_PAPER_REPLAY`, `paper_only=true` and `orders_enabled=false`; it doesn't open a GUI/server. No synthetic prices are inserted for ordinary use. CI fixtures use synthetic historical shapes and are not evidence of returns or trading edge.

## Limitations and testing

The replay covers at most the most recent 80 bars and processes at most 26 paper bars following 55-bar warmup. It is a narrow functional demonstration, **not** a statistically meaningful backtest. A Windows GUI manual visual check is still required; Linux CI tests the replay logic and read-only safety only.
