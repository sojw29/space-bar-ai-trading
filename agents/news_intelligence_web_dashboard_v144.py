"""V144 self-contained, offline-only HTML dashboard for V143 view-model JSON.

No CDN, external scripts, network, trading endpoints or dynamic HTML injection.
"""
import argparse
import html
import json
import math
from pathlib import Path

MAX_JSON_BYTES=4_000_000

def _safe(value):
    return html.escape(str(value),quote=True)

def _count(value):
    if type(value) is not int or value<0:
        raise ValueError("INVALID_COUNT")
    return value

def _metric(value):
    if value is None:
        return "N/A"
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError("INVALID_METRIC")
    return f"{value:+.4f}"

def render(data):
    if not isinstance(data,dict) or data.get("version")!="V143.0":
        raise ValueError("INVALID_DASHBOARD_DATA")
    cards=data.get("cards")
    charts=data.get("charts")
    warnings=data.get("warning_codes")
    metadata=data.get("metadata")
    if not isinstance(cards,list) or len(cards)>20 or not isinstance(charts,list) or len(charts)>300:
        raise ValueError("INVALID_DASHBOARD_ROWS")
    if not isinstance(warnings,list) or len(warnings)>100 or not isinstance(metadata,dict):
        raise ValueError("INVALID_DASHBOARD_METADATA")
    if data.get("data_freshness")!="STATIC_OFFLINE_SNAPSHOT":
        raise ValueError("UNSUPPORTED_DATA_FRESHNESS")
    cards_html=[]
    for card in cards:
        if not isinstance(card,dict) or not isinstance(card.get("label"),str):
            raise ValueError("INVALID_CARD")
        cards_html.append('<article class="card"><span>'+_safe(card["label"])+
                          '</span><strong>'+str(_count(card.get("value")))+"</strong></article>")
    rows=[]
    for row in charts:
        if not isinstance(row,dict) or not isinstance(row.get("category"),str) or row.get("horizon") not in ("5m","15m","60m"):
            raise ValueError("INVALID_CHART_ROW")
        before=_count(row.get("article_samples"))
        after=_count(row.get("adjusted_samples"))
        removed=_count(row.get("removed_samples"))
        if after>before or removed!=before-after:
            raise ValueError("INCONSISTENT_CHART_COUNTS")
        rows.append("<tr>"+"".join("<td>"+_safe(x)+"</td>" for x in (
            row["category"],row["horizon"],before,after,removed,
            _metric(row.get("mean_return_delta_percentage_points")),
            _metric(row.get("positive_rate_delta_percentage_points"))))+"</tr>")
    warning_html=[]
    for warning in warnings:
        if not isinstance(warning,str):
            raise ValueError("INVALID_WARNING")
        warning_html.append("<li>"+_safe(warning)+"</li>")
    topic=_safe(metadata.get("topic","UNKNOWN"))
    observed=_safe(metadata.get("observed_at","UNKNOWN"))
    verified="YES" if metadata.get("replay_verified_this_run") is True else "NOT CHECKED"
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>SPACE BAR | Offline News Intelligence</title>
<style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#0b1220;color:#e2e8f0}
body{max-width:1100px;margin:0 auto;padding:28px 18px}
h1{letter-spacing:.06em}h2{margin-top:34px;color:#93c5fd}
.note{border-left:4px solid #f59e0b;background:#1f2937;padding:12px 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.card{background:#172338;border:1px solid #334155;border-radius:12px;padding:20px}
.card span{display:block;color:#94a3b8;font-size:14px}.card strong{display:block;font-size:32px;margin-top:8px}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;background:#172338}
th,td{padding:11px;border-bottom:1px solid #334155;text-align:left;white-space:nowrap}
th{color:#93c5fd}li{margin:7px 0}small{color:#94a3b8}
</style></head><body>
<h1>SPACE BAR / NEWS INTELLIGENCE</h1>
<p class="note"><strong>STATIC OFFLINE RESEARCH ONLY.</strong> No live feed, trade signals, validated edge or order execution.</p>
<p>Topic: <strong>"""+topic+"""</strong> · Declared observation: <strong>"""+observed+"""</strong> · Exact replay: <strong>"""+verified+"""</strong></p>
<h2>Coverage Overview</h2><section class="grid">"""+"".join(cards_html)+"""</section>
<h2>Descriptive Article vs Group Comparison</h2>
<div class="table-wrap"><table><thead><tr>
<th>Category</th><th>Horizon</th><th>Articles</th><th>Groups</th><th>Removed</th>
<th>Mean delta (pp)</th><th>Positive-rate delta (pp)</th>
</tr></thead><tbody>"""+"".join(rows)+"""</tbody></table></div>
<h2>Research Warnings</h2><ul>"""+("".join(warning_html) or "<li>No extra warnings recorded; limitations still apply.</li>")+"""</ul>
<h2>Limitations</h2>
<p>GDELT seen time is not verified first publication or tradable availability.
Coverage groups are heuristic. Historical descriptive returns do not imply causal effects
or an executable trading strategy. Replay reproducibility is not independent data authenticity.</p>
<small>Offline, self-contained HTML generated from V143 JSON. No external resources.</small>
</body></html>
"""

def main():
    p=argparse.ArgumentParser(description="V144 self-contained offline news dashboard HTML")
    p.add_argument("v143_json",type=Path)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.v143_json.stat().st_size>MAX_JSON_BYTES:
        raise ValueError("INPUT_TOO_LARGE")
    data=json.loads(args.v143_json.read_text(encoding="utf-8"))
    output=render(data)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(output,encoding="utf-8")
    print(str(args.output))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
