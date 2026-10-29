"""V199 standalone offline HTML view of a V198 strategy scorecard.

No JavaScript, network, external dependencies, strategy ranking, or orders.
"""
import argparse
import html
import json
import math
from pathlib import Path

MAX_BYTES = 2_000_000


def _metric(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("INVALID_SCORECARD_METRIC")
    return html.escape(f"{value:.4f}")


def render(report):
    if not isinstance(report, dict) or report.get("version") != "V105.0":
        raise ValueError("INVALID_PIPELINE_REPORT")
    if report.get("research_only") is not True or report.get("orders_enabled") is not False or report.get("live_trading_approved") is not False:
        raise ValueError("UNSAFE_PIPELINE_REPORT")
    card = report.get("strategy_scorecard")
    if not isinstance(card, dict) or card.get("version") != "V197.0" or card.get("status") != "RESEARCH_COMPARISON_ONLY":
        raise ValueError("INVALID_SCORECARD")
    for key in ("ranking_enabled", "strategy_selection_enabled", "orders_allowed", "live_trading_approved"):
        if card.get(key) is not False:
            raise ValueError("UNSAFE_SCORECARD")
    if card.get("research_only") is not True:
        raise ValueError("UNSAFE_SCORECARD")
    rows = card.get("rows")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 30:
        raise ValueError("INVALID_SCORECARD_ROWS")
    output = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("strategy"), str):
            raise ValueError("INVALID_SCORECARD_ROW")
        name = row["strategy"]
        if not name or len(name) > 120 or name in seen:
            raise ValueError("INVALID_SCORECARD_IDENTITY")
        seen.add(name)
        trades = row.get("holdout_trades")
        if type(trades) is not int or trades < 0:
            raise ValueError("INVALID_TRADE_COUNT")
        if row.get("evidence_status") not in ("INSUFFICIENT_EVIDENCE", "EVIDENCE_REVIEWABLE"):
            raise ValueError("INVALID_EVIDENCE_STATUS")
        failures = row.get("evidence_failures")
        if not isinstance(failures, list) or len(failures) > 30 or any(not isinstance(x, str) or len(x) > 120 for x in failures):
            raise ValueError("INVALID_EVIDENCE_FAILURES")
        cells = [
            html.escape(name, quote=True), str(trades),
            _metric(row.get("holdout_win_rate_pct")),
            _metric(row.get("holdout_net_return_pct")),
            _metric(row.get("holdout_profit_factor")),
            _metric(row.get("holdout_max_drawdown_pct")),
            html.escape(row["evidence_status"]),
            html.escape(", ".join(failures) or "None"),
        ]
        output.append("<tr>" + "".join("<td>" + cell + "</td>" for cell in cells) + "</tr>")
    return """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>SPACE BAR | Offline Strategy Evidence</title>
<style>body{background:#0a1424;color:#e8f2ff;font:15px system-ui;margin:24px}
h1{color:#9de4ff}table{border-collapse:collapse;width:100%;min-width:850px}
th,td{padding:12px;border:1px solid #37536e;text-align:left}
th{background:#17314d}.scroll{overflow-x:auto}.warn{color:#ffcb83}
small{color:#a8c7db}</style></head><body>
<h1>SPACE BAR · Offline Strategy Scorecard</h1>
<p class="warn">RESEARCH ONLY · NO LIVE ORDERS · NO STRATEGY RANKING</p>
<div class="scroll"><table><thead><tr><th>Strategy</th><th>Holdout trades</th>
<th>Win rate %</th><th>Net return %</th><th>Profit factor</th>
<th>Max drawdown %</th><th>Evidence</th><th>Failures</th></tr></thead><tbody>""" + "".join(output) + """</tbody></table></div>
<p><small>Fixed assumed execution costs; spread, funding and variable liquidity excluded.
Holdout evidence is not independent proof of profitability or live readiness.
This static file never contacts an exchange.</small></p></body></html>"""


def main():
    parser = argparse.ArgumentParser(description="V199 offline scorecard HTML export")
    parser.add_argument("v198_json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.v198_json.is_file() or args.v198_json.stat().st_size > MAX_BYTES:
        raise ValueError("MISSING_OR_OVERSIZED_INPUT")
    data = json.loads(args.v198_json.read_text(encoding="utf-8"))
    output = render(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
