"""V124 bounded offline report snapshots and descriptive historical comparison.

No automatic learning, strategy updates, live execution or profitability approval.
"""
import argparse
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MAX_SNAPSHOTS = 100
METRICS = ("evaluated_folds", "abstained_folds", "positive_fold_rate_pct",
           "mean_fold_return_pct", "worst_fold_return_pct",
           "worst_fold_max_drawdown_pct", "hypothetical_sell_events")

def _snapshot(report, label):
    if not isinstance(report, dict) or report.get("version") != "V123.0":
        raise ValueError("INVALID_V123_REPORT")
    if not isinstance(label, str) or not label or len(label) > 100:
        raise ValueError("INVALID_LABEL")
    score = report.get("scorecard")
    if not isinstance(score, dict) or score.get("version") != "V121.0":
        raise ValueError("INVALID_SCORECARD")
    metrics = {}
    for key in METRICS:
        value = score.get(key)
        if value is not None and (isinstance(value, bool) or
                                  not isinstance(value, (int, float)) or
                                  not math.isfinite(value)):
            raise ValueError("INVALID_METRIC")
        metrics[key] = value
    raw = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {"label": label, "report_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "metrics": metrics}

def compare(old, new):
    if not isinstance(old, dict) or not isinstance(new, dict):
        raise ValueError("INVALID_SNAPSHOTS")
    changes = {}
    for key in METRICS:
        a = old["metrics"][key]
        b = new["metrics"][key]
        changes[key] = {"previous": a, "current": b,
                        "delta": round(b-a, 8) if a is not None and b is not None else None}
    return {"previous_label": old["label"], "current_label": new["label"],
            "changes": changes, "descriptive_only": True,
            "improvement_claim": False, "comparable_configuration_verified": False}

def record(report, history_path, label, recorded_at):
    if not isinstance(recorded_at, str):
        raise ValueError("INVALID_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("TIMESTAMP_MUST_HAVE_TIMEZONE")
    path = Path(history_path)
    if path.is_symlink():
        raise ValueError("SYMLINK_HISTORY_REJECTED")
    snapshots = []
    if path.exists():
        if path.stat().st_size > 2_000_000:
            raise ValueError("HISTORY_TOO_LARGE")
        try:
            snapshots = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("INVALID_HISTORY") from exc
        if not isinstance(snapshots, list) or len(snapshots) > MAX_SNAPSHOTS:
            raise ValueError("INVALID_HISTORY")
    item = _snapshot(report, label)
    item["recorded_at"] = parsed.isoformat()
    if any(x.get("report_sha256") == item["report_sha256"] and
           x.get("label") == label for x in snapshots if isinstance(x, dict)):
        return {"status": "DUPLICATE_UNCHANGED", "history_count": len(snapshots),
                "comparison": None, "simulation_only": True}
    previous = snapshots[-1] if snapshots else None
    result = compare(previous, item) if previous else None
    snapshots = (snapshots + [item])[-MAX_SNAPSHOTS:]
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".v124-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(snapshots, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return {"version": "V124.0", "status": "OFFLINE_REPORT_HISTORY_RECORDED",
            "history_count": len(snapshots), "comparison": result,
            "retention_limit": MAX_SNAPSHOTS, "research_only": True,
            "simulation_only": True, "exchange_connected": False,
            "orders_submitted_to_exchange": 0, "live_trading_approved": False,
            "validated_edge": False,
            "limitations": "Changes in summary metrics do not establish improvement. Configuration, symbols, periods and market conditions are not matched or verified. No automated learning or strategy updates."}

def main():
    parser = argparse.ArgumentParser(description="V124 offline report history comparison")
    parser.add_argument("report_json", type=Path)
    parser.add_argument("history_json", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--recorded-at", help="Timezone-aware ISO 8601; defaults to current UTC")
    args = parser.parse_args()
    report = json.loads(args.report_json.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    print(json.dumps(record(report, args.history_json, args.label, args.recorded_at or now),
                     indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
