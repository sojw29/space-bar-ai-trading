"""V113 isolated offline long-only paper ledger; zero exchange connectivity.

All fills are hypothetical. No leverage, shorts, margin, or real orders.
"""
import argparse
import json
import math
from decimal import Decimal, InvalidOperation, ROUND_DOWN

CENT = Decimal("0.01")
QTY = Decimal("0.00000001")
FEE = Decimal("0.00055")

def _positive(value, field):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("INVALID_" + field)
    try:
        x = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("INVALID_" + field) from exc
    if not x.is_finite() or x <= 0:
        raise ValueError("INVALID_" + field)
    return x

class PaperLedger:
    def __init__(self, initial_cash="10000", max_position_fraction="0.10",
                 max_daily_loss_fraction="0.05"):
        self.initial_cash = _positive(initial_cash, "CASH")
        self.cash = self.initial_cash
        self.units = Decimal("0")
        self.average_entry = Decimal("0")
        self.realized_pnl = Decimal("0")
        self.fees_paid = Decimal("0")
        self.events = []
        self.kill_switch = False
        self.max_position_fraction = _positive(max_position_fraction, "POSITION_LIMIT")
        self.max_daily_loss_fraction = _positive(max_daily_loss_fraction, "LOSS_LIMIT")
        if self.max_position_fraction > Decimal("0.10") or self.max_daily_loss_fraction > Decimal("0.05"):
            raise ValueError("UNSAFE_LIMIT")
        self.day_start_equity = self.initial_cash
        self.current_day = None
        self.last_price = None

    def _equity(self, price):
        return self.cash + self.units * price

    def _check_day(self, day, price):
        if not isinstance(day, str) or not day or len(day) > 32:
            raise ValueError("INVALID_DAY")
        if self.current_day is None:
            self.current_day = day
        elif day != self.current_day:
            if day < self.current_day:
                raise ValueError("NON_MONOTONIC_DAY")
            self.current_day = day
            self.day_start_equity = self._equity(price)

    def mark(self, price, day):
        price = _positive(price, "PRICE")
        self._check_day(day, price)
        self.last_price = price
        equity = self._equity(price)
        if equity < self.day_start_equity * (1-self.max_daily_loss_fraction):
            self.kill_switch = True
        return self.snapshot()

    def buy(self, price, budget, day):
        price = _positive(price, "PRICE")
        budget = _positive(budget, "BUDGET")
        self.mark(price, day)
        if self.kill_switch:
            raise ValueError("KILL_SWITCH_ACTIVE")
        equity = self._equity(price)
        if budget > self.cash or budget > equity*self.max_position_fraction:
            raise ValueError("POSITION_OR_CASH_LIMIT")
        if (self.units*price + budget) > equity*self.max_position_fraction:
            raise ValueError("AGGREGATE_POSITION_LIMIT")
        fee = (budget*FEE/(1+FEE)).quantize(CENT, rounding=ROUND_DOWN)
        notional = budget-fee
        units = (notional/price).quantize(QTY, rounding=ROUND_DOWN)
        if units <= 0:
            raise ValueError("ORDER_TOO_SMALL")
        used = units*price
        total = used+fee
        if total > self.cash:
            raise ValueError("INSUFFICIENT_CASH")
        self.average_entry = ((self.average_entry*self.units + used)/(self.units+units))
        self.cash -= total
        self.units += units
        self.fees_paid += fee
        self.events.append({"type":"BUY","day":day,"price":str(price),
                            "units":str(units),"fee":str(fee),
                            "cash_after":str(self.cash)})
        return self.snapshot()

    def sell(self, price, units, day):
        price = _positive(price, "PRICE")
        units = _positive(units, "UNITS")
        self.mark(price, day)
        # A loss-limit halt must block exposure increases, not trap existing
        # hypothetical positions. SELL is strictly reduction-only: no shorts.
        if units > self.units:
            raise ValueError("INSUFFICIENT_UNITS")
        gross = units*price
        fee = (gross*FEE).quantize(CENT, rounding=ROUND_DOWN)
        pnl = (price-self.average_entry)*units-fee
        self.cash += gross-fee
        self.units -= units
        self.realized_pnl += pnl
        self.fees_paid += fee
        if self.units == 0:
            self.average_entry = Decimal("0")
        self.events.append({"type":"SELL","day":day,"price":str(price),
                            "units":str(units),"fee":str(fee),
                            "cash_after":str(self.cash)})
        return self.snapshot()

    def snapshot(self):
        return {"version":"V113.0","cash":str(self.cash),"units":str(self.units),
                "average_entry":str(self.average_entry),
                "equity":str(self._equity(self.last_price)) if self.last_price else str(self.cash),
                "realized_pnl_before_entry_fees":str(self.realized_pnl),
                "fees_paid":str(self.fees_paid),"kill_switch":self.kill_switch,
                "event_count":len(self.events),
                "simulation_only":True,"exchange_connected":False,
                "orders_submitted_to_exchange":0,"live_trading_approved":False}

def run(commands):
    if not isinstance(commands, list) or len(commands) > 10000:
        raise ValueError("INVALID_COMMANDS")
    ledger = PaperLedger()
    for command in commands:
        if not isinstance(command, dict):
            raise ValueError("INVALID_COMMAND")
        action = command.get("action")
        if action == "MARK" and set(command) == {"action","price","day"}:
            ledger.mark(command["price"], command["day"])
        elif action == "BUY" and set(command) == {"action","price","budget","day"}:
            ledger.buy(command["price"], command["budget"], command["day"])
        elif action == "SELL" and set(command) == {"action","price","units","day"}:
            ledger.sell(command["price"], command["units"], command["day"])
        else:
            raise ValueError("UNKNOWN_COMMAND")
    return {"snapshot":ledger.snapshot(),"events":ledger.events}

def main():
    parser = argparse.ArgumentParser(description="V113 offline hypothetical paper ledger")
    parser.add_argument("commands_json")
    args = parser.parse_args()
    from pathlib import Path
    source = Path(args.commands_json)
    if not source.is_file() or source.stat().st_size > 1000000:
        raise ValueError("MISSING_OR_OVERSIZED_COMMANDS")
    print(json.dumps(run(json.loads(source.read_text(encoding="utf-8"))), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
