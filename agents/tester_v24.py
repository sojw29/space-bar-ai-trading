"""V24 consolidated research report; paper-only, never trading approval."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("reports")
OUT = ROOT / "v24"
SCENARIOS = ("BASE", "STRESS", "SEVERE")
METRICS = ("trades", "win_rate_pct", "return_pct", "profit_factor", "max_drawdown_pct")


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def numeric(value):
    if value is None or str(value).strip().lower() in ("", "none", "null", "nan", "inf", "-inf"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize(rows, v20=None, v21=None, v22=None):
    indexed = {}
    for row in rows:
        key = (row.get("candidate"), row.get("scenario"))
        if key in indexed:
            raise ValueError("Duplicate candidate/scenario row: " + str(key))
        if key[1] not in SCENARIOS or not key[0]:
            raise ValueError("Unexpected candidate/scenario: " + str(key))
        indexed[key] = row
    candidates = sorted({k[0] for k in indexed})
    expected = {(c, s) for c in candidates for s in SCENARIOS}
    missing = sorted(expected - set(indexed))
    warnings = []
    if missing:
        warnings.append("MISSING_SCENARIOS")
    if not rows:
        warnings.append("NO_SUMMARY_ROWS")
    if v20 is None:
        warnings.append("V20_AUDIT_UNAVAILABLE")
    if v21 is None:
        warnings.append("V21_RECONCILIATION_UNAVAILABLE")
    if v22 is None:
        warnings.append("V22_EVIDENCE_UNAVAILABLE")
    if v20 is not None and v20.get("errors"):
        warnings.append("V20_INTEGRITY_ERRORS")
    if v21 is not None and v21.get("status") == "RECONCILIATION_WARNING":
        warnings.append("TRADE_RECONCILIATION_WARNING")
    if v22 is not None and not v22.get("integrity_pass", False):
        warnings.append("V22_INTEGRITY_FAILED")
    records = []
    for candidate in candidates:
        values = {s: indexed.get((candidate, s)) for s in SCENARIOS}
        base, stress, severe = (values[s] for s in SCENARIOS)
        record = {"candidate": candidate}
        for scenario, row in values.items():
            for metric in METRICS:
                record[scenario.lower() + "_" + metric] = numeric(row.get(metric)) if row else None
        if all(values.values()):
            b = numeric(base.get("return_pct"))
            st = numeric(stress.get("return_pct"))
            sv = numeric(severe.get("return_pct"))
            record["cost_return_monotonic"] = (
                b >= st >= sv if all(v is not None for v in (b, st, sv)) else None
            )
            if record["cost_return_monotonic"] is False:
                warnings.append("NONMONOTONIC_COST_RETURNS_" + candidate)
        else:
            record["cost_return_monotonic"] = None
        records.append(record)
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "version": "V24.0",
        "candidates": records,
        "candidate_count": len(candidates),
        "scenario_row_count": len(rows),
        "missing_scenarios": [{"candidate": c, "scenario": s} for c, s in missing],
        "warnings": sorted(set(warnings)),
        "v20_audit_status": ("PASS" if v20.get("integrity_pass") is True else "FAIL")
        if v20 is not None else None,
        "v21_reconciliation_status": v21.get("status") if v21 else None,
        "v22_evidence_integrity_pass": v22.get("integrity_pass") if v22 else None,
        "independent_oos_verified": False,
        "live_trading_approved": False,
        "research_only": True,
    }


def render_markdown(report):
    lines = [
        "# SPACE BAR V24 — Consolidated Paper Research",
        "",
        "This report is retrospective research, **not independently verified OOS** and **not approval for live trading**.",
        "",
        "Generated (UTC): " + report["generated_utc"],
        "",
        "| Candidate | BASE return % | STRESS return % | SEVERE return % | BASE PF | STRESS PF | SEVERE PF | Trades (BASE) | Cost monotonic |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["candidates"]:
        keys = ("base_return_pct", "stress_return_pct", "severe_return_pct", "base_profit_factor",
                "stress_profit_factor", "severe_profit_factor", "base_trades")
        fields = [("N/A" if row.get(k) is None else str(round(row[k], 6))) for k in keys]
        lines.append("| " + row["candidate"] + " | " + " | ".join(fields) + " | " +
                     str(row["cost_return_monotonic"]) + " |")
    lines += ["", "## Evidence gates", "",
              "- V20 audit: " + str(report["v20_audit_status"]),
              "- V21 reconciliation: " + str(report["v21_reconciliation_status"]),
              "- V22 integrity pass: " + str(report["v22_evidence_integrity_pass"]),
              "- Warnings: " + (", ".join(report["warnings"]) or "none"),
              "",
              "Missing or undefined metrics are shown as N/A, not zero.",
              "A favorable historical result does not establish statistical significance or forward profitability."]
    return "\n".join(lines) + "\n"


def run():
    # Rebuild all upstream evidence before summarizing; do not silently trust stale files.
    import tester_v22
    tester_v22.run()
    report = summarize(
        read_csv(ROOT / "v17" / "summary.csv"),
        read_json(ROOT / "v20" / "audit.json"),
        read_json(ROOT / "v21" / "reconciliation.json"),
        read_json(ROOT / "v22" / "evidence.json"),
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT / "summary.md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))


if __name__ == "__main__":
    run()
