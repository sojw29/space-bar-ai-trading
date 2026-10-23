# V46 — Offline full-stack fault injection gates

This update enhances the simulated-only SPACE BAR research application with a **repeatable, offline, full-stack mocked REST + WebSocket integration contract**. The test passes the same completed BTC 5-minute candle through the production V38/V37/V27 analysis pipeline and the extracted V39 feed dispatcher into V42 simulated paper positions, V43 append-only SQLite snapshots, V44 read-only analytics and the localhost HTTP API.

V46 adds fault-injection tests ensuring a **journal storage failure halts** the simulated paper session, that a malformed or unsafe feed cannot silently create a simulated position, and that a reconnect status never silently reopens a previously halted paper session.

**No real Binance network connection is tested**, and no real orders or account credentials are used. All market candles and messages are synthetic; actual market execution, strategy profitability, independent out-of-sample validation, and long-term uptime remain unverified.

To run from repository root:

```bash
python agents/test_v45_integration.py
python agents/test_v46_failure_gates.py
```

GitHub Actions runs the new checks with previous paper safety tests. The new V45 integration test is a broader complementary fixture than the already-merged V45 smoke suite; it includes the persistent journal and localhost analytics contract.

No private exchange endpoints, broker accounts, API secrets, live-trading toggle, auto-orders or leverage are introduced. The research UI remains bound to `127.0.0.1`.
