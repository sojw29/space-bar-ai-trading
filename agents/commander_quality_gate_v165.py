"""V165: fail-closed quality gate for research-only AI meeting decisions.

Consumes V65's offline quality summary. Never authorizes orders or trading.
"""
import json
from pathlib import Path

EXPECTED_FILES = 9
VALID_DECISIONS = {"LONG", "SHORT", "WAIT"}


def gate_decision(decision, quality):
    """Return an auditable, non-executable meeting decision."""
    requested = str(decision).upper()
    if requested not in VALID_DECISIONS:
        requested = "WAIT"
    results = quality.get("results") if isinstance(quality, dict) else None
    valid_results = (
        isinstance(results, list)
        and len(results) == EXPECTED_FILES
        and all(isinstance(row, dict) for row in results)
    )
    trusted = (
        valid_results
        and quality.get("overall_status") == "PASS"
        and quality.get("research_usable") is True
        and all(row.get("status") == "PASS" and row.get("research_usable") is True
                for row in results)
    )
    return {
        "requested_decision": requested,
        "decision": requested if trusted else "WAIT",
        "quality_status": "PASS" if trusted else (
            quality.get("overall_status", "UNVERIFIED")
            if isinstance(quality, dict) else "UNVERIFIED"),
        "quality_verified": bool(trusted),
        "risk_veto": not trusted,
        "reason": "QUALITY_VERIFIED" if trusted else "DATA_QUALITY_NOT_VERIFIED",
        "research_only": True,
        "orders_enabled": False,
        "live_trading_approved": False,
    }


def from_report(path, decision):
    try:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        report = None
    return gate_decision(decision, report)
