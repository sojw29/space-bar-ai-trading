# V41 — Stateful closed-candle paper portfolio (research only)

The V41 `PaperPortfolio` is an **in-memory, hypothetical** portfolio-state model. It receives **completed 5m candle events and a matching V27 research envelope**, and can track one simulated position, paper cash, simulated transaction costs, entry/exit records and loss guard state.

**It is NOT connected to the live V39/V40 feed or to any account, exchange, trading service, or real-money order.** Future integration will require separate explicit review and tests. Importing the class does not initiate any network access or orders.

## Safety/logic

- Signal and candle timestamps must match; duplicate/gapped/invalid/incomplete bars **halt** processing until a fresh engine is initialized.
- Signals are derived from already **completed** bars. Any simulated entry happens at the close of that bar, which is a simplified *hypothetical close fill*, **not** a guaranteed executable price, and may be optimistic in live trading.
- A paper position is marked at each later bar's **close**. Simulated stop/take thresholds use closing prices (stop 0.6%, take 1.8% defaults), not protective stop orders; they can realize much larger losses during gaps. Exit fees and adverse slippage are applied.
- Paper exposure is capped at 20% of simulated cash per entry; no leverage, no pyramiding, no same-candle exit and re-entry.
- A daily equity loss guard defaults to 2%; breach halts the engine. It **cannot** guarantee a cap on losses when market moves gap past a threshold or during connectivity outages.
- Default simulated fee is 5.5bps and slippage 2bps **per side**. The model does not account for liquidation, funding, real broker fills, partial orders, intrabar fluctuations, spread changes, mark prices, exchange outages, latency, or accounting/tax considerations.
- No persistence: memory state is lost on process restart. No independent forward/out-of-sample trading performance is claimed.

## Local example (no network)

```python
from paper_portfolio_v41 import PaperPortfolio
portfolio = PaperPortfolio(initial_cash=10000, allocation=0.20)
# Supply each real verified, completed candle and a matching V27
# research envelope. See agents/test_v41_portfolio.py for examples.
# report = portfolio.on_completed_candle(candle, research_envelope)
```

Next engineering priorities: event-driven replay validation with realistic timing and independent forward capture, durable write-ahead ledger, strict reconciliation/clock-skew testing, and a read-only dashboard of **simulated** balances. Real-money order permission remains out of scope.
