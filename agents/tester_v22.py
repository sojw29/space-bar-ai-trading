"""V22 evidence gate: forward data provenance and replay stability (paper only).

Not an independent OOS test or exchange-execution ledger. It observes the
frozen V17 configuration and compares snapshots without approving trading.
"""
import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import history
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
    off_grid = 0
    for row in rows(path):
        timestamp = int(row["timestamp"])
        if timestamp % 300 != 0:
            off_grid += 1
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
        "off_grid_timestamps": off_grid,
    }


def forward_evidence_status(candles, issues, warnings=(), baseline_available=False):
    """Distinguish intact archives from actual post-cutoff observations."""
    if issues or candles.get("off_grid_timestamps", 0):
        return "INTEGRITY_FAILURE"
    if candles["forward_candle_count"] == 0:
        return "NO_FORWARD_CANDLES"
    if "NO_NEW_FORWARD_CANDLES" in warnings:
        return "NO_NEW_FORWARD_CANDLES"
    if candles["nonconsecutive_intervals"]:
        return "CANDLE_GAPS_REQUIRE_REVIEW"
    if not baseline_available:
        return "NO_PRIOR_FORWARD_BASELINE"
    return "FORWARD_CANDLES_PRESENT_UNVERIFIED"


def forward_evidence_usable_for_research(candles, issues, warnings=(), baseline_available=False):
    """Only newly extended, gap-free forward snapshots may be used as research evidence."""
    return forward_evidence_status(candles, issues, warnings, baseline_available) == "FORWARD_CANDLES_PRESENT_UNVERIFIED"


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


def history_policy():
    return {"source": "BINANCE_USDT_FUTURES_ARCHIVES",
            "publication_delay_days": history.PUBLICATION_DELAY_DAYS,
            "window_days": history.DAYS_TO_COLLECT}


def valid_prior_shape(prior):
    return isinstance(prior, dict) and isinstance(prior.get("candles"), dict)


def load_previous_evidence(path):
    """A missing artifact is optional; an existing corrupt artifact is an error."""
    if not path.exists():
        return None
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise RuntimeError("INVALID_PRIOR_EVIDENCE_JSON") from error
    if not valid_prior_shape(prior):
        raise RuntimeError("INVALID_PRIOR_EVIDENCE_SCHEMA")
    return prior


def compare_forward_snapshot(prior, current_last):
    """Compare only snapshots collected under the same explicit archive policy."""
    if prior is None:
        return [], ["NO_PRIOR_FORWARD_BASELINE"], False
    if not valid_prior_shape(prior):
        return ["INVALID_PRIOR_EVIDENCE_SCHEMA"], [], False
    if prior.get("history_policy") != history_policy():
        return [], ["PRIOR_HISTORY_POLICY_INCOMPARABLE", "NO_PRIOR_FORWARD_BASELINE"], False
    previous_last = prior.get("candles", {}).get("last_forward_candle_utc")
    if not previous_last:
        return [], ["NO_PRIOR_FORWARD_BASELINE"], False
    try:
        if not isinstance(previous_last, str):
            raise ValueError("INVALID_TIMESTAMP_TYPE")
        previous_time = datetime.fromisoformat(previous_last)
        if previous_time.utcoffset() is None:
            raise ValueError("NAIVE_TIMESTAMP")
    except (ValueError, TypeError):
        return ["INVALID_PRIOR_FORWARD_TIMESTAMP"], [], False
    if not current_last:
        return ["FORWARD_DATA_REGRESSION"], [], True
    try:
        if not isinstance(current_last, str):
            raise ValueError("INVALID_TIMESTAMP_TYPE")
        current_time = datetime.fromisoformat(current_last)
        if current_time.utcoffset() is None:
            raise ValueError("NAIVE_TIMESTAMP")
    except (ValueError, TypeError):
        return ["INVALID_CURRENT_FORWARD_TIMESTAMP"], [], False
    if current_time < previous_time:
        return ["FORWARD_DATA_REGRESSION"], [], True
    if current_time == previous_time:
        return [], ["NO_NEW_FORWARD_CANDLES"], True
    return [], [], True


def publish_evidence(report):
    target = OUT / "evidence.json"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=".evidence.json.", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, indent=2, allow_nan=False)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run():
    target = OUT / "evidence.json"
    prior_path = previous_evidence_path()
    # Reject aliases before clearing stale output; the prior input must survive.
    if prior_path.resolve() == target.resolve() or (
        prior_path.exists() and target.exists() and os.path.samefile(prior_path, target)
    ):
        raise ValueError("INPUT_OUTPUT_PATH_COLLISION")
    # Never leave an earlier PASS report available after a failed rerun.
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidence.json").unlink(missing_ok=True)
    v21.run()
    source = Path(v17.REPORT_DIR)
    protocol_path = source / "protocol.json"
    trades_path = source / "trades.csv"
    summary_path = source / "summary.csv"
    if not CANDLE_PATH.exists():
        raise RuntimeError("Missing BTC 5m source data")
    candles = inspect_candles(CANDLE_PATH, v17.CUTOFF)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    summaries = rows(summary_path)
    prior = load_previous_evidence(prior_path)
    issues = []
    warnings = []
    if candles["duplicate_or_unsorted_timestamps"]:
        issues.append("DUPLICATE_OR_UNSORTED_CANDLES")
    if candles["off_grid_timestamps"]:
        issues.append("OFF_GRID_CANDLE_TIMESTAMPS")
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
    comparison_issues, comparison_warnings, baseline_available = compare_forward_snapshot(prior, current_last)
    issues.extend(comparison_issues)
    warnings.extend(comparison_warnings)
    if prior and prior.get("cutoff_utc") != protocol.get("cutoff_utc"):
        issues.append("PRIOR_CUTOFF_MISMATCH")
    report = {
        "version": "V22.0",
        "history_policy": history_policy(),
        "prior_evidence_comparable": baseline_available,
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
        "forward_evidence_status": forward_evidence_status(candles, issues, warnings, baseline_available),
        "forward_evidence_available": candles["forward_candle_count"] > 0,
        "forward_evidence_usable_for_research": forward_evidence_usable_for_research(candles, issues, warnings, baseline_available),
        "independent_oos_verified": False,
        "live_trading_approved": False,
        "limitations": [
            "Previous artifacts are not tamper-proof; snapshots are retrospective replays.",
            "End-of-data force-closes and data revisions can alter trade results.",
            "No live order execution, frozen external timestamp attestation, or independent OOS certification.",
        ],
    }
    publish_evidence(report)
    print("V22 data integrity:", "PASS" if not issues else "FAIL")
    print("V22 forward evidence:", report["forward_evidence_status"])
    print("Forward candles:", candles["forward_candle_count"], "prior:", bool(prior))
    for item in issues:
        print("ERROR:", item)
    for item in warnings:
        print("WARNING:", item)
    if issues:
        raise RuntimeError("V22 evidence integrity failure: " + ", ".join(issues))


if __name__ == "__main__":
    run()
