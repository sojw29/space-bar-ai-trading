"""V36 deterministic offline one-candle paper fill simulator.

Research only: historical replay, not prospective OOS or live trading.
Signals use completed bar i-1; paper entry uses following bar i open;
exit uses same bar i close. No position overlap, orders, API keys, or broker.
"""
import argparse
import json
from pathlib import Path

import multi_agent_v26 as agents
from dashboard_api_v28 import DEFAULT_HISTORY, load_candles

SCHEMA = "36.0"


def simulate(candles, *, fee_bps=5.5, slippage_bps=2.0, notional=100.0):
    """One-bar, non-compounding hypothetical fills; costs charged both sides.

    The approach deliberately does not trade on the signal candle's close.
    Costs are applied adversely to both entry and exit.
    """
    for label, value in (("fee_bps", fee_bps), ("slippage_bps", slippage_bps),
                         ("notional", notional)):
        agents._safe_number(value, label)
    if not 0 <= fee_bps <= 100 or not 0 <= slippage_bps <= 100:
        raise ValueError("Fee and slippage must be in [0, 100] basis points")
    if not 0 < notional <= 1_000_000:
        raise ValueError("Notional must be >0 and <=1,000,000")
    agents.validate(candles)
    trades = []
    total_pnl = 0.0
    fee_rate = fee_bps / 10000
    slip_rate = slippage_bps / 10000
    # Each i-1 decision uses only bars <= i-1; next bar i is not yet
    # available to the agent when deciding.
    for i in range(55, len(candles)):
        report = agents.analyze(candles[:i])
        decision = report["commander"]["decision"]
        if decision == "WAIT":
            continue
        bar = candles[i]
        opening = float(bar["open"])
        closing = float(bar["close"])
        if decision == "LONG":
            entry = opening * (1 + slip_rate)
            exit_price = closing * (1 - slip_rate)
            gross_return = exit_price / entry - 1
        else:
            entry = opening * (1 - slip_rate)
            exit_price = closing * (1 + slip_rate)
            gross_return = 1 - exit_price / entry
        # Both sides: hypothetical notional-based fees; no leverage.
        pnl = notional * (gross_return - 2 * fee_rate)
        total_pnl += pnl
        trades.append({
            "signal_candle_utc": report["last_closed_candle_utc"],
            "fill_candle_timestamp": bar["timestamp"],
            "side": decision,
            "paper_entry": round(entry, 8),
            "paper_exit": round(exit_price, 8),
            "paper_notional": notional,
            "fee_bps_per_side": fee_bps,
            "slippage_bps_per_side": slippage_bps,
            "net_pnl": round(pnl, 8),
            "mode": "HISTORICAL_PAPER_SIMULATION",
        })
    return {
        "schema_version": SCHEMA,
        "mode": "HISTORICAL_PAPER_SIMULATION",
        "independent_oos_verified": False,
        "realized_account_pnl": False,
        "orders_enabled": False,
        "live_trading_approved": False,
        "fill_model": "next_open_to_same_candle_close_with_adverse_slippage",
        "trades": trades,
        "trade_count": len(trades),
        "net_pnl_total": round(total_pnl, 8),
        "pnl_unit": "hypothetical_quote_currency",
        "note": "Illustrative historical replay, no order book, fills or latency modeled.",
    }


def main():
    p = argparse.ArgumentParser(description="Offline, no-broker V36 paper fill simulator")
    p.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    p.add_argument("--fee-bps", type=float, default=5.5)
    p.add_argument("--slippage-bps", type=float, default=2.0)
    p.add_argument("--notional", type=float, default=100.0)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = simulate(load_candles(args.history, limit=120),
                      fee_bps=args.fee_bps, slippage_bps=args.slippage_bps,
                      notional=args.notional)
    content = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n", encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()
