"""V22 evidence gate: forward data provenance and replay stability (paper only).

Not an independent OOS test or exchange-execution ledger. It observes the
frozen V17 configuration and compares snapshots without approving trading.
"""
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import tester_v21 as v21
import tester_v17 as v17

OUT = Path("reports/v22")
PREVIOUS = Path(os.environ.get("V22_PREVIOUS_DIR", "previous_v22"))
CANDLE_PATH = Path("data/history/BTC_5m.csv")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def inspect_candles(path, cutoff):
    count = 0
    first = last = None
    previous = None
    gaps = 0
    duplicates = 0
    for row in rows(path):
        timestamp = int(row["timestamp"])
        if previous is not None:
            if timestamp <= previous:
                duplicates += 1
            elif timestamp - previous != 300:
                gaps += 1
        previous = timestamp
        if timestamp >= cutoff:
            count += 1
            if first is None:
                first = timestamp
            last = timestamp
    return {
        "forward_candle_count": count,
        "first_forward_candle_utc": v17.utc(first) if first is not None else None,
        "last_forward_candle_utc": v17.utc(last) if last is not None else None,
        "nonconsecutive_intervals": gaps,
        "duplicate_or_unsorted_timestamps": duplicates,
    }


def previous_evidence_path():
    """Resolve both supported artifact ZIP layouts, never current-run files."""
    configured = PREVIOUS / "evidence.json"
    if configured.exists() or os.environ.get("V22_PREVIOUS_DIR"):
        return configured
    for candidate in (PREVIOUS / "v22" / "evidence.json",
                      PREVIOUS / "reports" / "v22" / "evidence.json"):
        if candidate.exists():
            return candidate
    return configured


def run():
    v21.run()
    OUT.mkdir(parents=True, exist_ok=True)
    source = Path(v17.REPORT_DIR)
    protocol_path = source / "protocol.json"
    trades_path = source / "trades.csv"
    summary_path = source / "summary.csv"
    if not CANDLE_PATH.exists():
        raise RuntimeError("Missing BTC 5m source data")
    candles = inspect_candles(CANDLE_PATH, v17.CUTOFF)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    summaries = rows(summary_path)
    prior_path = previous_evidence_path()
    prior = json.loads(prior_path.read_text(encoding="utf-8")) if prior_path.exists() else None
    issues = []
    warnings = []
    if candles["duplicate_or_unsorted_timestamps"]:
        issues.append("DUPLICATE_OR_UNSORTED_CANDLES")
    if candles["nonconsecutive_intervals"]:
        warnings.append("HISTORICAL_CANDLE_GAPS")
    if candles["forward_candle_count"] == 0:
        warnings.append("NO_POST_CUTOFF_CANDLES")
    if protocol.get("cutoff_utc") != v17.utc(v17.CUTOFF):
        issues.append("CUTOFF_DRIFT")
    if len(summaries) != len(v17.CANDIDATES) * len(v17.SCENARIOS):
        issues.append("SUMMARY_CARDINALITY_MISMATCH")
    final_candle_utc = v17.utc(int(rows(CANDLE_PATH)[-1]["timestamp"]))
    for row in summaries:
        if row["last_candle_utc"] != final_candle_utc:
            issues.append("SUMMARY_CANDLE_END_MISMATCH")
            break
    previous_last = prior.get("candles", {}).get("last_forward_candle_utc") if prior else None
    current_last = candles["last_forward_candle_utc"]
    if prior and previous_last and (not current_last or current_last < previous_last):
        issues.append("FORWARD_DATA_REGRESSION")
    if prior and previous_last == current_last:
        warnings.append("NO_NEW_FORWARD_CANDLES")
    if prior and prior.get("cutoff_utc") != protocol.get("cutoff_utc"):
        issues.append("PRIOR_CUTOFF_MISMATCH")
    report = {
        "version": "V22.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "cutoff_utc": protocol.get("cutoff_utc"),
        "candles": candles,
        "prior_evidence_available": bool(prior),
        "prior_evidence_source": str(prior_path) if prior_path.exists() else None,
        "prior_last_forward_candle_utc": previous_last,
        "input_sha256": {
            "candles": sha(CANDLE_PATH),
            "protocol": sha(protocol_path),
            "trades": sha(trades_path),
            "summary": sha(summary_path),
        },
        "errors": sorted(set(issues)),
        "warnings": sorted(set(warnings)),
        "integrity_pass": not issues,
        "independent_oos_verified": False,
        "live_trading_approved": False,
        "limitations": [
            "Previous artifacts are not tamper-proof; snapshots are retrospective replays.",
            "End-of-data force-closes and data revisions can alter trade results.",
            "No live order execution, frozen external timestamp attestation, or independent OOS certification.",
        ],
    }
    (OUT / "evidence.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("V22 evidence gate:", "PASS" if not issues else "FAIL")
    print("Forward candles:", candles["forward_candle_count"], "prior:", bool(prior))
    for item in issues:
        print("ERROR:", item)
    for item in warnings:
        print("WARNING:", item)
    if issues:
        raise RuntimeError("V22 evidence integrity failure: " + ", ".join(issues))


if __name__ == "__main__":
    run()
