"""V186: fail-closed validation of offline meeting snapshots.

No exchange access, orders, or live-trading activation.
"""
import re

SHA256 = re.compile(r"^[a-f0-9]{64}$")


def validate_meeting_snapshot(snapshot):
    """Return an auditable verdict; malformed input never raises or approves."""
    failures = []
    if not isinstance(snapshot, dict):
        return {"verified": False, "status": "BLOCKED", "failures": ["invalid_snapshot"]}

    evidence = snapshot.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    if not (
        evidence.get("source") == "offline_v65_quality_report"
        and isinstance(evidence.get("sha256"), str)
        and SHA256.fullmatch(evidence["sha256"])
        and type(evidence.get("bytes")) is int
        and evidence["bytes"] > 0
        and evidence.get("verified") is True
    ):
        failures.append("invalid_evidence")

    gate = snapshot.get("quality_gate")
    gate = gate if isinstance(gate, dict) else {}
    if not (
        gate.get("quality_verified") is True
        and gate.get("quality_status") == "PASS"
        and gate.get("risk_veto") is False
    ):
        failures.append("quality_gate_blocked")

    agents = snapshot.get("agents")
    agents = agents if isinstance(agents, dict) else {}
    atlas = agents.get("ATLAS")
    guardian = agents.get("GUARDIAN")
    commander = agents.get("COMMANDER")
    if not (
        isinstance(atlas, dict) and atlas.get("state") == "DATA_VERIFIED"
        and isinstance(guardian, dict) and guardian.get("state") == "CLEAR"
        and isinstance(commander, dict) and commander.get("decision") == "WAIT"
    ):
        failures.append("agent_contract_blocked")

    if not (
        snapshot.get("research_only") is True
        and snapshot.get("orders_enabled") is False
        and snapshot.get("live_trading_approved") is False
    ):
        failures.append("unsafe_mode")

    return {
        "verified": not failures,
        "status": "VERIFIED_RESEARCH" if not failures else "BLOCKED",
        "failures": failures,
        "orders_allowed": False,
        "live_trading_allowed": False,
    }
