"""SPACE BAR V17 — fixed-hypothesis forward observation (paper only).

Protocol frozen in code: BTC 5m, signal settings inherited from V15.
Historical data through 2026-10-18 23:55 UTC was previously inspected.
Only entries on/after 2026-10-19 00:00 UTC are counted as forward observations.
A snapshot is NOT an immutable live execution record. Repeated snapshots overlap.
No trading approval; no automatic parameter tuning.
"""
import csv
import hashlib
import json
import os
from datetime import datetime, timezone

import tester_v10 as v10
import tester_v11 as v11
import tester_v14 as v14
import tester_v15 as v15
from tester import load_data, prepare

CUTOFF = int(datetime(2026, 10, 19, tzinfo=timezone.utc).timestamp())
CANDIDATES = ("ADX25_30_ATR015_025", "V15_BASELINE")
SCENARIOS = (
    ("BASE", 0.00055, 0.00020),
    ("STRESS", 0.00100, 0.00050),
    ("SEVERE", 0.00150, 0.00100),
)
MIN_TRADES = 30
REPORT_DIR = "reports/v17"


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def forward_window_label(candles):
    """Do not describe an empty post-cutoff window as a backwards date range."""
    last = candles[-1]["timestamp"]
    if last < CUTOFF:
        return ("V17 FORWARD SNAPSHOT | NO_FORWARD_CANDLES | cutoff "
                + utc(CUTOFF) + " | data ends " + utc(last))
    return "V17 FORWARD SNAPSHOT | " + utc(CUTOFF) + " to " + utc(last)


def write_csv(filename, rows, fields):
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, filename), "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def loss_streak(trades):
    current = worst = 0
    for trade in trades:
        if trade["net_pnl_usd"] < 0:
            current += 1
            worst = max(worst, current)
        else:
            current = 0
    return worst


def run():
    v15.validate_configs()
    candles = load_data("BTC", "5")
    if not candles:
        raise RuntimeError("BTC 5m data unavailable")
    v14.validate_history(candles)
    indices = [i for i, candle in enumerate(candles) if candle["timestamp"] >= CUTOFF]
    first = indices[0] if indices else len(candles)
    if first and candles[first - 1]["timestamp"] >= CUTOFF:
        raise RuntimeError("Cutoff boundary invalid")
    config_by_name = {c["name"]: c for c in v15.CONFIGS}
    indicators = prepare(candles)
    htf = v10.build_htf_filter(candles)
    atr = v11.calculate_atr_pct(candles, period=14)
    original_signal, original_atr = v10.get_v10_signal, v15.ACTIVE_ATR
    rows, trades_out = [], []
    try:
        v10.get_v10_signal = v15.v15_signal_adapter
        v15.ACTIVE_ATR = atr
        for candidate in CANDIDATES:
            for scenario, fee, slip in SCENARIOS:
                # No entry before the cutoff; pre-cutoff bars are indicator warmup only.
                if first >= len(candles):
                    metrics = v15.calculate_metrics([])
                    trade_log = []
                else:
                    result = v10.simulate(
                        candles, indicators, htf, config_by_name[candidate],
                        first, len(candles), fee, slip, "FORWARD_SNAPSHOT", scenario,
                    )
                    metrics = v15.calculate_metrics([result])
                    trade_log = metrics["trade_log"]
                    if any(t["entry_time"] < CUTOFF for t in trade_log):
                        raise RuntimeError("Pre-cutoff entry leaked into forward window")
                for trade in trade_log:
                    trades_out.append({"candidate": candidate, "scenario": scenario, **trade})
                count = metrics["trades"]
                rows.append({
                    "candidate": candidate, "scenario": scenario,
                    "cutoff_utc": utc(CUTOFF),
                    "last_candle_utc": utc(candles[-1]["timestamp"]),
                    "observed_bars": len(indices),
                    "trades": count,
                    "win_rate_pct": metrics["win_rate_pct"],
                    "return_pct": metrics["return_pct"],
                    "profit_factor": metrics["profit_factor"],
                    "max_drawdown_pct": metrics["max_drawdown_pct"],
                    "max_consecutive_losses": loss_streak(trade_log),
                    "sample_status": "MINIMUM_REACHED_NOT_APPROVED" if count >= MIN_TRADES else "INSUFFICIENT_TRADES",
                    "independent_oos_verified": False,
                    "live_trading_approved": False,
                })
    finally:
        v10.get_v10_signal = original_signal
        v15.ACTIVE_ATR = original_atr

    write_csv("summary.csv", rows, [
        "candidate", "scenario", "cutoff_utc", "last_candle_utc", "observed_bars",
        "trades", "win_rate_pct", "return_pct", "profit_factor", "max_drawdown_pct",
        "max_consecutive_losses", "sample_status", "independent_oos_verified",
        "live_trading_approved",
    ])
    write_csv("trades.csv", trades_out, ["candidate", *v10.TRADE_FIELDS])
    protocol = {
        "version": "V17.0", "symbol": "BTCUSDT", "timeframe": "5m",
        "cutoff_utc": utc(CUTOFF), "candidates": {
            name: config_by_name[name] for name in CANDIDATES
        }, "scenarios": SCENARIOS, "min_trades": MIN_TRADES,
        "data_last_candle_utc": utc(candles[-1]["timestamp"]),
        "method": "rolling retrospective snapshot after fixed cutoff; no execution log",
        "caveat": "Post-cutoff data may have been inspected; independence not certified",
        "note": "V10 forcibly closes open positions at the last available candle (END); snapshot returns can change as data extends",
        "live_orders": False,
    }
    raw = json.dumps(protocol, sort_keys=True, indent=2).encode("utf-8")
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "protocol.json"), "wb") as handle:
        handle.write(raw)
    print(forward_window_label(candles))
    print("Protocol SHA256:", hashlib.sha256(raw).hexdigest())
    for row in rows:
        print(row["candidate"], row["scenario"], "trades", row["trades"],
              "return", row["return_pct"], "PF", row["profit_factor"],
              "status", row["sample_status"])
    print("PAPER RESEARCH ONLY. NO INDEPENDENT OOS CERTIFICATION OR LIVE TRADING APPROVAL.")


if __name__ == "__main__":
    run()
