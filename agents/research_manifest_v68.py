"""V68: verify offline report bundle consistency and SHA-256 provenance.

This verifies local reports only. It never collects data or authorizes orders.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REPORTS = (("v63", "diagnostics.json"), ("v64", "archive_lag.json"),
           ("v65", "quality.json"), ("v66", "health.json"))

def inspect_bundle(root):
    records, issues = {}, []
    timestamps = set()
    for version, filename in REPORTS:
        path = root / version / filename
        try:
            data = path.read_bytes()
            payload = json.loads(data)
            if not isinstance(payload, dict) or payload.get("version") != version.upper() + ".0":
                raise ValueError("WRONG_REPORT_VERSION")
            generated = payload.get("generated_utc")
            if not isinstance(generated, str):
                raise ValueError("MISSING_GENERATION_TIME")
            stamp = datetime.fromisoformat(generated.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("NAIVE_GENERATION_TIME")
            timestamps.add(stamp.astimezone(timezone.utc).isoformat())
            if payload.get("live_trading_approved") is not False:
                raise ValueError("LIVE_APPROVAL_NOT_EXPLICITLY_FALSE")
            records[version] = {"path": f"{version}/{filename}",
                                "sha256": hashlib.sha256(data).hexdigest(),
                                "generated_utc": generated}
        except (OSError, ValueError, TypeError) as exc:
            issues.append(f"{version.upper()}_INVALID_OR_MISSING:{exc}")
    if len(timestamps) > 1:
        issues.append("MIXED_REPORT_GENERATION_TIMES")
    return {"version": "V68.0", "status": "BLOCKED" if issues else "CONSISTENT_BUNDLE",
            "issues": sorted(issues), "reports": records,
            "research_only": True, "live_trading_approved": False,
            "note": "Hashes detect later file changes; they do not authenticate market data or prove profitability."}

def main():
    parser = argparse.ArgumentParser(description="Offline report provenance verifier")
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--output", type=Path, default=Path("reports/v68/manifest.json"))
    args = parser.parse_args()
    result = inspect_bundle(args.reports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
