"""V19 observation quality audit — paper-only, no strategy tuning or orders.

Consumes V18's rolling monitoring report, not an independent OOS execution log.
No-trade observations are valid; profit factor is undefined for zero trades.
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import tester_v18 as v18

OUT = Path("reports/v19")
EXPECTED = {(c, s) for c in v18.CANDIDATES for s in v18.SCENARIOS}


def parse_float(value):
    if value is None or str(value).strip().lower() in ("", "none", "null", "nan"):
        return None
    return float(value)


def evaluate(rows):
    if len(rows) != len(EXPECTED):
        raise ValueError("Unexpected number of V18 monitoring rows")
    seen = set()
    output = []
    for row in rows:
        key = (row["candidate"], row["scenario"])
        if key not in EXPECTED or key in seen:
            raise ValueError("Unexpected or duplicate candidate/scenario: " + repr(key))
        seen.add(key)
        n = int(row["trades"])
        pf = parse_float(row["profit_factor"])
        ret = parse_float(row["return_pct"])
        previous_n = int(row["previous_trades"]) if row.get("previous_trades", "").strip() else None
        flags = [f for f in row.get("flags", "").split("|") if f and f != "OBSERVATION_ONLY"]
        if n == 0:
            flags.append("NO_OBSERVED_TRADES")
        if n > 0 and pf is None:
            flags.append("UNDEFINED_PROFIT_FACTOR")
        if n < v18.MIN_TRADES:
            flags.append("NOT_ENOUGH_TRADES_FOR_ASSESSMENT")
        if previous_n is not None and n == previous_n:
            flags.append("NO_NEW_CLOSED_TRADES")
        if ret is None:
            flags.append("UNDEFINED_RETURN")
        output.append({
            "candidate": key[0], "scenario": key[1],
            "last_candle_utc": row["last_candle_utc"],
            "trades": n, "previous_trades": previous_n if previous_n is not None else "",
            "profit_factor": pf, "return_pct": ret,
            "quality_flags": "|".join(dict.fromkeys(flags)) or "OBSERVATION_ONLY",
            "assessment": "DESCRIPTIVE_ONLY" if n >= v18.MIN_TRADES else "INSUFFICIENT_SAMPLE",
            "independent_oos_verified": False,
            "live_trading_approved": False,
        })
    return output


def run():
    v18.build()
    with (v18.OUT / "monitor.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    results = evaluate(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "quality.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    summary = {
        "version": "V19.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "candidates": list(v18.CANDIDATES),
        "scenarios": list(v18.SCENARIOS),
        "minimum_trades_for_descriptive_assessment": v18.MIN_TRADES,
        "rows": results,
        "notes": [
            "V17/V18/V19 snapshots overlap and may force-close positions at data end.",
            "No independent out-of-sample verification or immutable forward execution ledger.",
            "A passing workflow is not evidence of strategy profitability.",
            "No parameter tuning, no live trading, no automatic trading approval.",
        ],
        "live_trading_approved": False,
    }
    (OUT / "quality.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for row in results:
        print(row["candidate"], row["scenario"], "trades", row["trades"],
              "PF", row["profit_factor"], "status", row["assessment"],
              "flags", row["quality_flags"], flush=True)
    print("V19 COMPLETE — observation quality only; no live trading approval.")


if __name__ == "__main__":
    run()
