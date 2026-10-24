"""V99 local Windows/desktop preflight. Read-only except isolated temporary files."""
import argparse
import importlib.util
import json
import platform
import sys
import tempfile
from pathlib import Path

MODULES = ("tkinter", "json", "pathlib", "threading")
SCRIPTS = ("unified_launcher_v97.py", "readiness_desktop_v96.py",
           "integration_verifier_v98.py")

def preflight(repo=None):
    root = Path(repo).resolve() if repo else Path(__file__).resolve().parent.parent
    agents = root / "agents"
    checks = []
    def add(code, passed, detail):
        checks.append({"code": code, "status": "PASS" if passed else "BLOCKED",
                       "detail": detail})
    add("PYTHON_VERSION", sys.version_info >= (3, 11),
        "Python 3.11 or newer required for supported CI environment.")
    for name in MODULES:
        try:
            found = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            found = False
        add("MODULE_" + name.upper(), found, "Standard library module: " + name)
    for name in SCRIPTS:
        file = agents / name
        add("SCRIPT_" + name.removesuffix(".py").upper(),
            file.is_file() and file.stat().st_size > 0,
            "Required local launcher/verification script: " + name)
    add("SUPPORTED_OS", platform.system() in ("Windows", "Linux", "Darwin"),
        "Desktop OS detected; graphical desktop session is not verified.")
    try:
        with tempfile.TemporaryDirectory(prefix="spacebar-v99-") as d:
            target = Path(d) / "write-check.txt"
            target.write_text("offline-only", encoding="utf-8")
            storage_ok = target.read_text(encoding="utf-8") == "offline-only"
    except OSError:
        storage_ok = False
    add("TEMP_STORAGE", storage_ok, "Isolated temporary storage write/read check.")
    status = "ENVIRONMENT_PASS" if all(c["status"] == "PASS" for c in checks) else "BLOCKED"
    return {"version": "V99.0", "status": status, "checks": checks,
            "passed": sum(c["status"] == "PASS" for c in checks),
            "total": len(checks), "platform": platform.system(),
            "python": ".".join(map(str, sys.version_info[:3])),
            "research_only": True, "live_trading_approved": False,
            "scope": "LOCAL_DESKTOP_PREFLIGHT_ONLY",
            "note": "Passing preflight does not validate GUI display, strategies or trading."}

def main():
    parser = argparse.ArgumentParser(description="SPACE BAR AI offline desktop preflight")
    parser.add_argument("--repo", type=Path)
    args = parser.parse_args()
    result = preflight(args.repo)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ENVIRONMENT_PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
