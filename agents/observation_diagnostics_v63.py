"""V63 read-only observation diagnostics. No trading, orders, or optimization."""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None

def diagnose(audit, evidence, reconciliation, readiness, now=None, max_age_hours=120):
    now = now or datetime.now(timezone.utc)
    errors, warnings = [], []
    last = parse_time((audit or {}).get("observed_last_candle_utc"))
    age = (now - last).total_seconds() / 3600 if last else None
    if age is None or not math.isfinite(age):
        errors.append("LAST_CANDLE_TIME_UNAVAILABLE")
    elif age < 0:
        errors.append("FUTURE_LAST_CANDLE")
    elif age > max_age_hours:
        warnings.append("STALE_CANDLES")
    for name, report in (("V20", audit), ("V22", evidence)):
        if not isinstance(report, dict) or report.get("integrity_pass") is not True:
            errors.append(name + "_INTEGRITY_NOT_VERIFIED")
    counts = (reconciliation or {}).get("current_finalized_by_candidate_scenario")
    if not isinstance(counts, dict):
        warnings.append("FINALIZED_COUNTS_UNAVAILABLE")
        counts = {}
    total = 0
    for candidate, scenarios in counts.items():
        if not isinstance(scenarios, dict):
            errors.append("INVALID_FINALIZED_COUNTS")
            continue
        for scenario, value in scenarios.items():
            if type(value) is not int or value < 0:
                errors.append("INVALID_FINALIZED_COUNTS")
            else:
                total += value
    if total == 0:
        warnings.append("NO_FINALIZED_SAMPLES")
    if not isinstance(readiness, dict) or not isinstance(readiness.get("candidates"), list):
        warnings.append("READINESS_UNAVAILABLE")
    return {
        "version": "V63.0", "generated_utc": now.isoformat(),
        "last_candle_utc": last.isoformat() if last else None,
        "data_age_hours": round(age, 2) if age is not None and math.isfinite(age) else None,
        "finalized_scenario_samples_total": total,
        "errors": sorted(set(errors)), "warnings": sorted(set(warnings)),
        "status": "FAIL" if errors else "NEEDS_MORE_EVIDENCE" if warnings else "OBSERVATION_ONLY",
        "independent_oos_verified": False, "live_trading_approved": False,
    }

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

def main():
    parser = argparse.ArgumentParser(description="Read-only V63 research diagnostics")
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--output", type=Path, default=Path("reports/v63/diagnostics.json"))
    args = parser.parse_args()
    root = args.reports
    result = diagnose(read_json(root / "v20/audit.json"),
                      read_json(root / "v22/evidence.json"),
                      read_json(root / "v21/reconciliation.json"),
                      read_json(root / "v25/readiness.json"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if result["errors"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
