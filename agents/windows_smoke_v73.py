"""V73 offline Windows-friendly environment smoke check; never starts trading."""
import argparse
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path

REQUIRED_MODULES = ("json", "hashlib", "datetime", "pathlib")

def inspect_environment(repo_root, reports_dir=None):
    repo_root = Path(repo_root).resolve()
    reports_dir = Path(reports_dir).resolve() if reports_dir else repo_root / "reports"
    checks = {}
    checks["python_supported"] = sys.version_info >= (3, 11)
    checks["required_stdlib_available"] = all(importlib.util.find_spec(x) is not None for x in REQUIRED_MODULES)
    checks["agents_directory_exists"] = (repo_root / "agents").is_dir()
    checks["v72_cli_exists"] = (repo_root / "agents/local_status_v72.py").is_file()
    checks["reports_parent_exists"] = reports_dir.parent.is_dir()
    checks["reports_dir_exists"] = reports_dir.is_dir()
    warnings = []
    if not checks["reports_dir_exists"]:
        warnings.append("REPORTS_DIRECTORY_MISSING_RUN_RESEARCH_PIPELINE_FIRST")
    blockers = [key.upper() for key in ("python_supported", "required_stdlib_available",
                                         "agents_directory_exists", "v72_cli_exists",
                                         "reports_parent_exists") if not checks[key]]
    return {"version": "V73.0", "platform": platform.system(),
            "python": platform.python_version(), "checks": checks,
            "status": "BLOCKED" if blockers else "REVIEW" if warnings else "ENVIRONMENT_READY",
            "blockers": blockers, "warnings": warnings,
            "research_only": True, "live_trading_approved": False,
            "note": "Environment readiness is not report health, trading approval or profit validation."}

def main():
    parser = argparse.ArgumentParser(description="Offline local environment smoke check")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = inspect_environment(args.repo, args.reports)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("SPACE BAR AI | LOCAL ENVIRONMENT:", result["status"])
        for name, ok in result["checks"].items():
            print(("PASS" if ok else "CHECK"), name)
        for issue in result["blockers"] + result["warnings"]:
            print("NOTICE:", issue)
        print("Live trading: DISABLED")
    return 1 if result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
