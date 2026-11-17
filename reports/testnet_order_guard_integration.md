# Bybit testnet order guard: integration boundary

This PR adds `agents/testnet_order_guard.py` as an **isolated policy check**. It does **not** connect to Bybit, send orders, read API keys, or alter the local dashboard.

## Verified scope
- Explicit opt-in flags must both be the literal string `true`.
- Environment must be `testnet` and base URL must exactly match `https://api-testnet.bybit.com`.
- Only the enumerated symbols and Buy/Sell directions are accepted.
- Quantity must be finite, positive and at most 0.01 (preliminary cap, **not** an exchange instrument filter).
- Offline unit tests run on pull requests.

## Do not wire this to an order sender yet
Before any testnet adapter is introduced, reconcile this guard with existing V310/V311/V312 dry-run, idempotency and intent-ledger code. Establish one authoritative policy, not two independently switchable gates. Verify that instrument-specific minimum quantity, quantity step, notional, leverage, position mode, reduce-only, risk limits, rate limits and account permissions are validated against the testnet exchange metadata. Do not persist credentials in the repository, logs, or reports.

The local dashboard's GET-only research interface and POST 405 behavior must remain unchanged. Never allow a dashboard request or AI meeting result to trigger exchange orders. Any future execution adapter requires separate review, offline mocked integration tests, a testnet-only manual activation flow, and an independent emergency kill switch.

## Verification
```bash
PYTHONPATH=. python -m unittest discover -s tests -p 'test_testnet_order_guard.py' -v
```

A green unit test is **not** evidence that exchange integration or actual order placement is safe.
