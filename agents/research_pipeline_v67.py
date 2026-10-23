"""V67 single-command OFFLINE diagnostics pipeline. Never fetches or trades."""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from observation_diagnostics_v63 import diagnose, read_json
from archive_lag_v64 import SYMBOLS, TIMEFRAMES, diagnose_file
from data_quality_v65 import score_file
from research_health_v66 import aggregate

def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".v67-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def run(data_dir, reports_dir, now=None):
    now = now or datetime.now(timezone.utc)
    r = reports_dir
    v63 = diagnose(read_json(r / "v20/audit.json"),
                   read_json(r / "v22/evidence.json"),
                   read_json(r / "v21/reconciliation.json"),
                   read_json(r / "v25/readiness.json"), now=now)
    paths = [(data_dir / f"{coin}_{tf}m.csv", tf)
             for coin in SYMBOLS for tf in TIMEFRAMES]
    v64 = {"version": "V64.0", "generated_utc": now.isoformat(),
           "archive_delay_is_expected_not_realtime": True,
           "results": [diagnose_file(path, tf, now) for path, tf in paths],
           "live_trading_approved": False}
    v65 = {"version": "V65.0", "generated_utc": now.isoformat(),
           "results": [score_file(path, tf, now) for path, tf in paths],
           "research_only": True, "independent_oos_verified": False,
           "live_trading_approved": False}
    v66 = aggregate(v63, v64, v65, now=now)
    for version, name, payload in (("v63", "diagnostics.json", v63),
                                   ("v64", "archive_lag.json", v64),
                                   ("v65", "quality.json", v65),
                                   ("v66", "health.json", v66)):
        atomic_json(r / version / name, payload)
    return v66

def main():
    parser = argparse.ArgumentParser(description="Offline V63-V66 pipeline; no exchange access")
    parser.add_argument("--data-dir", type=Path, default=Path("data/history"))
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    args = parser.parse_args()
    result = run(args.data_dir, args.reports)
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
