"""V25 evidence readiness assessment. Not a trading signal or approval."""
import json
from datetime import datetime, timezone
from pathlib import Path

import tester_v24 as v24

OUT = Path("reports/v25")
MIN_TRADES = 30


def evaluate(report, evidence, reconciliation):
    blockers = []
    if evidence is None or not evidence.get("integrity_pass", False):
        blockers.append("EVIDENCE_INTEGRITY_UNVERIFIED")
    if evidence is None or not evidence.get("prior_evidence_available", False):
        blockers.append("NO_PRIOR_EVIDENCE_SNAPSHOT")
    if reconciliation is None or not reconciliation.get("previous_snapshot_available", False):
        blockers.append("NO_PRIOR_TRADE_SNAPSHOT")
    if reconciliation is not None and reconciliation.get("status") == "RECONCILIATION_WARNING":
        blockers.append("TRADE_RECORD_REVISIONS")
    if report.get("warnings"):
        blockers.append("UPSTREAM_REPORT_WARNINGS")
    candidates = []
    for row in report.get("candidates", []):
        reasons = list(blockers)
        for scenario in ("base", "stress", "severe"):
            n = row.get(scenario + "_trades")
            if n is None or n < MIN_TRADES:
                reasons.append("INSUFFICIENT_" + scenario.upper() + "_TRADES")
            ret = row.get(scenario + "_return_pct")
            pf = row.get(scenario + "_profit_factor")
            if ret is None or pf is None:
                reasons.append("UNDEFINED_" + scenario.upper() + "_PERFORMANCE")
        if row.get("cost_return_monotonic") is not True:
            reasons.append("COST_STABILITY_NOT_DEMONSTRATED")
        candidates.append({
            "candidate": row["candidate"],
            "sample_minimum_met": all(
                row.get(s + "_trades") is not None and row[s + "_trades"] >= MIN_TRADES
                for s in ("base", "stress", "severe")
            ),
            "observation_quality_status": "NEEDS_MORE_EVIDENCE" if reasons else "PRELIMINARY_RESEARCH_ONLY",
            "reasons": sorted(set(reasons)),
            "independent_oos_verified": False,
            "live_trading_approved": False,
        })
    return {
        "version": "V25.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "minimum_trades_per_scenario": MIN_TRADES,
        "candidates": candidates,
        "independent_oos_verified": False,
        "live_trading_approved": False,
        "note": "Even PRELIMINARY_RESEARCH_ONLY is not independent OOS certification or permission to trade.",
    }


def run():
    v24.run()
    report = v24.read_json(Path("reports/v24/summary.json"))
    evidence = v24.read_json(Path("reports/v22/evidence.json"))
    reconciliation = v24.read_json(Path("reports/v21/reconciliation.json"))
    assessment = evaluate(report, evidence, reconciliation)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "readiness.json").write_text(json.dumps(assessment, indent=2), encoding="utf-8")
    print("V25 paper evidence readiness")
    for row in assessment["candidates"]:
        print(row["candidate"], row["observation_quality_status"], "|", ",".join(row["reasons"]))
    print("NO INDEPENDENT OOS VERIFICATION OR LIVE TRADING APPROVAL.")


if __name__ == "__main__":
    run()
