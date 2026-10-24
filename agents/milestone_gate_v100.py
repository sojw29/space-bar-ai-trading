"""V100 offline research milestone gate. No exchange access or live orders."""
import argparse
import json
from environment_preflight_v99 import preflight
from integration_verifier_v98 import verify

def milestone(repo=None):
    environment = preflight(repo)
    integration = verify()
    checks = [
        {"code": "DESKTOP_PREFLIGHT", "status": "PASS" if environment["status"] == "ENVIRONMENT_PASS" else "BLOCKED"},
        {"code": "OFFLINE_INTEGRATION", "status": "PASS" if integration["status"] == "INTEGRATION_PASS" else "BLOCKED"},
        {"code": "TRADING_REMAINS_DISABLED", "status": "PASS" if environment["live_trading_approved"] is False and integration["live_trading_approved"] is False else "BLOCKED"},
    ]
    passed = sum(c["status"] == "PASS" for c in checks)
    return {
        "version": "V100.0",
        "status": "OFFLINE_MILESTONE_PASS" if passed == len(checks) else "BLOCKED",
        "checks": checks, "passed": passed, "total": len(checks),
        "environment": environment, "integration": integration,
        "research_only": True, "live_trading_approved": False,
        "real_orders_enabled": False,
        "scope": "OFFLINE_DIAGNOSTICS_AND_REPORTING",
        "not_validated": [
            "strategy profitability", "autonomous AI learning",
            "long-running paper trading", "exchange order execution",
            "GUI interaction on user PC", "real-time mobile monitoring",
        ],
    }

def main():
    parser = argparse.ArgumentParser(description="SPACE BAR AI V100 offline milestone check")
    parser.add_argument("--repo", type=str, default=None)
    args = parser.parse_args()
    result = milestone(args.repo)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "OFFLINE_MILESTONE_PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
