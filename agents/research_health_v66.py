"""V66 offline research system health aggregation. Never authorizes trading."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None

def aggregate(v63, v64, v65, now=None):
    now = now or datetime.now(timezone.utc)
    blockers, warnings = [], []
    if not isinstance(v63, dict) or v63.get("version") != "V63.0":
        blockers.append("V63_REPORT_MISSING_OR_INVALID")
    else:
        if v63.get("status") == "FAIL" or v63.get("errors"):
            blockers.append("V63_EVIDENCE_FAILURE")
        elif v63.get("status") != "OBSERVATION_ONLY":
            warnings.append("V63_MORE_EVIDENCE_NEEDED")
    for version, report in (("V64", v64), ("V65", v65)):
        if not isinstance(report, dict) or report.get("version") != version + ".0":
            blockers.append(version + "_REPORT_MISSING_OR_INVALID")
            continue
        rows = report.get("results")
        if not isinstance(rows, list) or len(rows) != 9:
            blockers.append(version + "_INCOMPLETE_SYMBOL_TIMEFRAMES")
            continue
        keys = [(str(r.get("path", "")).split("/")[-1], r.get("timeframe_minutes"))
                for r in rows if isinstance(r, dict)]
        expected = {(f"{symbol}_{tf}m.csv", tf) for symbol in ("BTC", "ETH", "SOL")
                    for tf in (1, 5, 15)}
        if set(keys) != expected or len(keys) != len(set(keys)):
            blockers.append(version + "_UNEXPECTED_DATASET_KEYS")
        for r in rows:
            if not isinstance(r, dict):
                blockers.append(version + "_INVALID_ROW")
                continue
            status = r.get("status")
            if status in ("ERROR", "FAIL", "UNVERIFIED") or status is None:
                blockers.append(version + "_DATA_FAILURE")
            elif status in ("WARNING", "REVIEW"):
                warnings.append(version + "_DATA_REVIEW")
            elif status not in ("ON_EXPECTED_ARCHIVE_CUTOFF", "PASS"):
                blockers.append(version + "_UNKNOWN_STATUS")
    return {"version": "V66.0", "generated_utc": now.isoformat(),
            "status": "BLOCKED" if blockers else "REVIEW" if warnings else "RESEARCH_DATA_CHECKS_PASS",
            "blockers": sorted(set(blockers)), "warnings": sorted(set(warnings)),
            "research_only": True, "independent_oos_verified": False,
            "live_trading_approved": False,
            "note": "Passing checks do not prove predictive value or profitability."}

def main():
    parser = argparse.ArgumentParser(description="Offline V66 research readiness")
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--output", type=Path, default=Path("reports/v66/health.json"))
    args = parser.parse_args()
    r = args.reports
    result = aggregate(read_json(r / "v63/diagnostics.json"),
                       read_json(r / "v64/archive_lag.json"),
                       read_json(r / "v65/quality.json"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
