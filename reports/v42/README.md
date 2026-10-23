# V42 — Opt-in local paper-monitor dashboard

V42 adds **simulated-only** stateful portfolio tracking to the V39/V40 localhost read-only research dashboard. It is disabled by default. No account credentials, private exchange calls, broker/API orders, or real funds can be accessed. It is **not independently validated prospective trading performance**.

### Launch from repository root

```bash
python -m pip install websocket-client
python agents/live_dashboard_v39.py --port 8765 --fast-warmup --paper-monitor
```

Open `http://127.0.0.1:8765/` **on the same machine**. `--fast-warmup` remains optional; without it, the public WebSocket needs at least 55 consecutive closed 5m bars before a research event. All exchange calls are public-market-data only, and both options are explicit opt-in. Geographic endpoint restrictions and clock skew may prevent connection.

### Flow

1. The public-only V38 feed emits each completed, integrity-checked BTC 5m candle **alongside** its V27 agent/COMMANDER research envelope.
2. V39 continues to show research state and emits a read-only `GET /api/v1/agents`.
3. If `--paper-monitor` is supplied, V42 passes the matching observation and candle to V41's **in-memory paper-only** position state machine.
4. `GET /api/v1/paper` exposes simulated cash, optional closing-mark equity, a single hypothetical position, realized paper P&L, event count and HALTED reason. The existing dashboard shows these metrics in a new **Paper Portfolio** panel. Without the flag, that endpoint returns 404 and the panel displays *미활성화*.
5. On a lost connection, data gap, malformed/mismatched candle, unacceptable latency, stale mark, or risk guard breach, the **paper monitor latches HALTED**. Its mark-to-close equity is hidden when stale. Restart with a deliberately new session; this version does not automatically recreate or reconcile pre-existing exposure.

### Limitations / important warnings

The V41 position engine assumes fills at the same completed candle's close, applies a fixed approximate fee/slippage, and checks stop/take thresholds only at closing prices. This can be materially optimistic and does not model actual fills, intrabar stop execution, spreads, queue priority, funding, liquidation, latency, exchange outages, account margin or real capital loss. **All P&L is simulated.** State is lost on shutdown. This is not a persistent paper brokerage account and is not authorized to trade.

`/api/v1/paper` is deliberately read-only. Never expose the unauthenticated local server beyond `127.0.0.1`.

CI uses injected-clock/mock public events and loopback HTTP; **no live exchange connectivity is tested in Actions**.
