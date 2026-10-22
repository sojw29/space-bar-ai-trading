"""SPACE BAR V20: audit data integrity and comparability, not profitability.

Runs the frozen V17 -> V18 -> V19 paper pipeline and checks its outputs.
Snapshots overlap and can force-close positions; no independent OOS claim.
"""
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import tester_v19 as v19
import tester_v18 as v18
import tester_v17 as v17

OUT = Path("reports/v20")
EXPECTED = {(c, s) for c in v17.CANDIDATES for s, _, _ in v17.SCENARIOS}


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(value):
    if value is None or str(value).strip().lower() in ("", "none", "null", "nan"):
        return None
    result = float(value)
    if not math.isfinite(result):
        return None
    return result


def audit():
    v19.run()
    source = Path(v17.REPORT_DIR)
    summary_path = source / "summary.csv"
    trades_path = source / "trades.csv"
    protocol_path = source / "protocol.json"
    quality_path = v19.OUT / "quality.csv"
    summary = read_csv(summary_path)
    trades = read_csv(trades_path)
    quality = read_csv(quality_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    errors, warnings = [], []
    if len(summary) != len(EXPECTED):
        errors.append("MISSING_OR_DUPLICATED_SUMMARY_ROWS")
    by_key = {}
    for row in summary:
        key = (row["candidate"], row["scenario"])
        if key not in EXPECTED or key in by_key:
            errors.append("INVALID_SUMMARY_KEY:" + str(key))
        by_key[key] = row
    if set(by_key) != EXPECTED:
        errors.append("MISSING_SUMMARY_KEY")
    if protocol.get("cutoff_utc") != v17.utc(v17.CUTOFF):
        errors.append("PROTOCOL_CUTOFF_CHANGED")
    if protocol.get("live_orders") is not False:
        errors.append("LIVE_ORDER_FLAG_INVALID")
    for row in summary:
        if row["cutoff_utc"] != v17.utc(v17.CUTOFF):
            errors.append("SUMMARY_CUTOFF_CHANGED")
        if row["live_trading_approved"].lower() != "false":
            errors.append("LIVE_APPROVAL_FLAG_INVALID")
        if row["independent_oos_verified"].lower() != "false":
            errors.append("OOS_FLAG_INVALID")
        if int(row["trades"]) < v17.MIN_TRADES:
            warnings.append(row["candidate"] + "/" + row["scenario"] + ":LOW_SAMPLE")
        if number(row["profit_factor"]) is None:
            warnings.append(row["candidate"] + "/" + row["scenario"] + ":UNDEFINED_PF")
    counts = {}
    for trade in trades:
        key = (trade["candidate"], trade["scenario"])
        counts[key] = counts.get(key, 0) + 1
        ts = number(trade.get("entry_time"))
        if ts is None or ts < v17.CUTOFF:
            errors.append("INVALID_TRADE_ENTRY_TIME")
    for key in EXPECTED:
        if key in by_key and counts.get(key, 0) != int(by_key[key]["trades"]):
            errors.append("TRADE_COUNT_MISMATCH:" + str(key))
    if len(quality) != len(EXPECTED):
        errors.append("QUALITY_ROW_COUNT_MISMATCH")
    last = datetime.fromisoformat(summary[0]["last_candle_utc"])
    age_days = (datetime.now(timezone.utc) - last).total_seconds() / 86400
    if age_days > 5:
        warnings.append("DATA_STALE_OVER_5_DAYS")
    if age_days < -1:
        errors.append("DATA_FROM_FUTURE")
    for candidate in v17.CANDIDATES:
        # Costs cannot be compared trade-by-trade when exit timing/number changes.
        for scenario in ("BASE", "STRESS", "SEVERE"):
            row = by_key.get((candidate, scenario))
            if row and number(row["return_pct"]) is None:
                warnings.append(candidate + "/" + scenario + ":UNDEFINED_RETURN")
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = [summary_path, trades_path, protocol_path, quality_path]
    manifest = {
        "version": "V20.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "observed_last_candle_utc": last.isoformat(),
        "data_age_days": round(age_days, 3),
        "expected_candidate_scenarios": len(EXPECTED),
        "trade_rows": len(trades),
        "integrity_pass": not errors,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "input_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        "independent_oos_verified": False,
        "live_trading_approved": False,
        "caveat": "Rolling retrospective snapshots overlap; terminal force-close and historical inspection prevent independent OOS certification.",
    }
    (OUT / "audit.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with (OUT / "audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["kind", "message"])
        writer.writeheader()
        for msg in manifest["errors"]:
            writer.writerow({"kind": "ERROR", "message": msg})
        for msg in manifest["warnings"]:
            writer.writerow({"kind": "WARNING", "message": msg})
        if not manifest["errors"] and not manifest["warnings"]:
            writer.writerow({"kind": "INFO", "message": "NO_FINDINGS"})
    print("V20 INTEGRITY", "PASS" if not errors else "FAIL")
    print("DATA AGE DAYS", round(age_days, 3), "TRADE ROWS", len(trades))
    for msg in manifest["errors"]:
        print("ERROR", msg)
    for msg in manifest["warnings"]:
        print("WARNING", msg)
    print("PAPER RESEARCH ONLY — NO LIVE TRADING APPROVAL")
    if errors:
        raise RuntimeError("V20 integrity audit failed: " + "; ".join(sorted(set(errors))))


if __name__ == "__main__":
    audit()
