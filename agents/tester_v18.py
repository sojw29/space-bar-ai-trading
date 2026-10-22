"""V18 longitudinal monitoring of V17 rolling snapshots (paper research only).

Compares completed V17 snapshots across GitHub Actions runs. This is NOT an
independent OOS or immutable execution ledger. V10 may force-close at data end,
so returns and trade counts can change when the data window extends.
"""
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import tester_v17 as v17

OUT = Path("reports/v18")
PREVIOUS = Path(os.environ.get("V18_PREVIOUS_DIR", "previous_v18"))
CANDIDATES = v17.CANDIDATES
SCENARIOS = tuple(s[0] for s in v17.SCENARIOS)
MIN_TRADES = v17.MIN_TRADES


def read_rows(path):
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    result = {}
    for row in rows:
        key = (row["candidate"], row["scenario"])
        if key in result:
            raise ValueError("Duplicate candidate/scenario: " + str(key))
        result[key] = row
    return result


def number(row, key):
    return float(row[key])


def build():
    v17.run()
    current = read_rows(Path(v17.REPORT_DIR) / "summary.csv")
    previous = read_rows(PREVIOUS / "summary.csv")
    if set(current) != {(c, s) for c in CANDIDATES for s in SCENARIOS}:
        raise RuntimeError("V17 snapshot is missing candidate/scenario rows")
    rows, warnings = [], []
    for candidate in CANDIDATES:
        for scenario in SCENARIOS:
            key = (candidate, scenario)
            now = current[key]
            old = previous.get(key)
            n = int(now["trades"])
            pf = number(now, "profit_factor")
            ret = number(now, "return_pct")
            dd = number(now, "max_drawdown_pct")
            flags = []
            if n < MIN_TRADES:
                flags.append("INSUFFICIENT_TRADES")
            if n >= MIN_TRADES and (pf < 1.0 or ret <= 0):
                flags.append("NEGATIVE_PERFORMANCE")
            if scenario == "SEVERE" and n >= MIN_TRADES and (pf < 1.0 or ret <= 0):
                flags.append("SEVERE_COST_FAILURE")
            if old:
                if now["cutoff_utc"] != old["cutoff_utc"]:
                    flags.append("CUTOFF_CHANGED")
                if now["last_candle_utc"] <= old["last_candle_utc"]:
                    flags.append("NO_NEW_DATA")
                if n < int(old["trades"]):
                    flags.append("TRADE_COUNT_DECREASED")
                if n >= MIN_TRADES and pf < number(old, "profit_factor") - 0.25:
                    flags.append("PF_DETERIORATION")
                if n >= MIN_TRADES and ret < number(old, "return_pct") - 0.5:
                    flags.append("RETURN_DETERIORATION")
            else:
                flags.append("NO_PREVIOUS_SNAPSHOT")
            if flags:
                warnings.append({"candidate": candidate, "scenario": scenario, "flags": flags})
            rows.append({
                "candidate": candidate, "scenario": scenario,
                "last_candle_utc": now["last_candle_utc"],
                "trades": n, "win_rate_pct": now["win_rate_pct"],
                "return_pct": ret, "profit_factor": pf,
                "max_drawdown_pct": dd,
                "max_consecutive_losses": now["max_consecutive_losses"],
                "previous_trades": old["trades"] if old else "",
                "previous_return_pct": old["return_pct"] if old else "",
                "previous_profit_factor": old["profit_factor"] if old else "",
                "delta_return_pct": round(ret - number(old, "return_pct"), 6) if old else "",
                "delta_profit_factor": round(pf - number(old, "profit_factor"), 6) if old else "",
                "flags": "|".join(flags) if flags else "OBSERVATION_ONLY",
                "independent_oos_verified": False,
                "live_trading_approved": False,
            })
    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with (OUT / "monitor.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with (OUT / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(next(iter(current.values()))))
        writer.writeheader()
        writer.writerows(current.values())
    manifest = {
        "version": "V18.0", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "previous_snapshot_found": bool(previous),
        "cutoff_utc": next(iter(current.values()))["cutoff_utc"],
        "warnings": warnings,
        "disclaimer": "Overlapping retrospective snapshots; end-of-data forced close; not independent OOS, not live execution.",
        "live_trading_approved": False,
    }
    (OUT / "monitor.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for row in rows:
        print(row["candidate"], row["scenario"], "trades", row["trades"],
              "PF", row["profit_factor"], "flags", row["flags"], flush=True)
    print("V18 COMPLETE — monitoring only; no live trading approval.")


if __name__ == "__main__":
    build()
