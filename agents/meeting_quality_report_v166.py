"""V166: offline read-only meeting quality report for the 3D room.

This produces a JSON snapshot only. It never places orders.
"""
import argparse
import json
from pathlib import Path
from commander_quality_gate_v165 import from_report


def build_report(quality_path):
    gate = from_report(quality_path, "WAIT")
    return {
        "version": "V166.0",
        "room": "SPACE BAR AI MEETING",
        "agents": {
            "ATLAS": {"state": "DATA_VERIFIED" if gate["quality_verified"] else "DATA_UNVERIFIED"},
            "GUARDIAN": {"state": "CLEAR" if not gate["risk_veto"] else "VETO"},
            "COMMANDER": {"decision": gate["decision"], "reason": gate["reason"]},
        },
        "quality_gate": gate,
        "research_only": True,
        "orders_enabled": False,
        "live_trading_approved": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate offline AI meeting quality snapshot")
    parser.add_argument("--quality", type=Path, default=Path("reports/v65/quality.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/v166/meeting.json"))
    args = parser.parse_args()
    report = build_report(args.quality)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
