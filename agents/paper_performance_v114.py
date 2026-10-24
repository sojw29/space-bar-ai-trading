"""V114 offline paper-ledger performance timeline and drawdown audit.

Replays hypothetical commands in order. No network, credentials or real orders.
"""
import argparse
import json
from decimal import Decimal
from pathlib import Path

from offline_paper_ledger_v113 import PaperLedger

MAX_COMMANDS = 10000
MAX_FILE_BYTES = 1000000

def analyze(commands):
    if not isinstance(commands, list) or len(commands) > MAX_COMMANDS:
        raise ValueError("INVALID_COMMANDS")
    ledger = PaperLedger()
    peak = ledger.initial_cash
    worst_drawdown = Decimal("0")
    timeline = []
    for index, command in enumerate(commands):
        if not isinstance(command, dict):
            raise ValueError("INVALID_COMMAND")
        action = command.get("action")
        if action == "MARK" and set(command) == {"action", "price", "day"}:
            ledger.mark(command["price"], command["day"])
        elif action == "BUY" and set(command) == {"action", "price", "budget", "day"}:
            ledger.buy(command["price"], command["budget"], command["day"])
        elif action == "SELL" and set(command) == {"action", "price", "units", "day"}:
            ledger.sell(command["price"], command["units"], command["day"])
        else:
            raise ValueError("UNKNOWN_COMMAND")
        equity = ledger._equity(ledger.last_price)
        peak = max(peak, equity)
        drawdown = (peak-equity)/peak*100
        worst_drawdown = max(worst_drawdown, drawdown)
        timeline.append({
            "command_index": index, "day": command["day"], "action": action,
            "equity": str(equity), "cash": str(ledger.cash),
            "units": str(ledger.units), "drawdown_pct": str(drawdown),
            "kill_switch": ledger.kill_switch,
        })
    final_equity = ledger._equity(ledger.last_price) if ledger.last_price else ledger.initial_cash
    buy_count = sum(event["type"] == "BUY" for event in ledger.events)
    sell_count = sum(event["type"] == "SELL" for event in ledger.events)
    return {
        "version": "V114.0", "status": "OFFLINE_HYPOTHETICAL_PERFORMANCE",
        "initial_equity": str(ledger.initial_cash),
        "final_equity": str(final_equity),
        "total_return_pct": str((final_equity/ledger.initial_cash-1)*100),
        "max_drawdown_pct": str(worst_drawdown),
        "fees_paid": str(ledger.fees_paid),
        "hypothetical_buy_events": buy_count,
        "hypothetical_sell_events": sell_count,
        "hypothetical_mark_events": len(commands)-buy_count-sell_count,
        "kill_switch_active": ledger.kill_switch,
        "timeline": timeline, "final_snapshot": ledger.snapshot(),
        "simulation_only": True, "exchange_connected": False,
        "orders_submitted_to_exchange": 0, "live_trading_approved": False,
        "limitations": "Mark-to-market uses provided prices; no spreads, slippage, latency, partial fills, persistence, or verified market data. Drawdown is sampled at commands, not continuously.",
    }

def run(path):
    source = Path(path)
    if not source.is_file() or source.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("MISSING_OR_OVERSIZED_COMMANDS")
    try:
        commands = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_COMMANDS_JSON") from exc
    return analyze(commands)

def main():
    parser = argparse.ArgumentParser(description="V114 offline hypothetical performance timeline")
    parser.add_argument("commands_json")
    args = parser.parse_args()
    print(json.dumps(run(args.commands_json), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
