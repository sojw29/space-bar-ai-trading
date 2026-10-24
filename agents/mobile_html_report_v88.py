"""V88 offline mobile-friendly HTML report from a sanitized V87 JSON snapshot.

Does not host a web server, send data or enable trading.
"""
import argparse
import html
import json
import os
import tempfile
from pathlib import Path

EXPECTED_SCHEMA = "spacebar.local-status.v87"
STATUSES = {"BLOCKED", "REVIEW", "LOCAL_STATUS_PASS",
            "LOCAL_DIAGNOSTICS_PASS", "ANALYZED", "INSUFFICIENT_DATA"}
MAX_BYTES = 131072

def _status(value):
    return value if isinstance(value, str) and value in STATUSES else "REVIEW"

def _timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        return "UNKNOWN"
    return html.escape(value, quote=True)

def render(payload):
    if not isinstance(payload, dict) or payload.get("schema") != EXPECTED_SCHEMA:
        raise ValueError("INVALID_STATUS_SCHEMA")
    if payload.get("live_trading_approved") is not False or payload.get("transport") != "LOCAL_FILE_ONLY":
        raise ValueError("UNSAFE_STATUS_PAYLOAD")
    overall = _status(payload.get("overall_status"))
    fields = [("Overall", overall), ("PC", _status(payload.get("pc_status"))),
              ("Audit", _status(payload.get("audit_status"))),
              ("History", _status(payload.get("history_status")))]
    cards = "".join(
        '<section class="card"><div class="label">' + html.escape(label) +
        '</div><strong>' + html.escape(value) + '</strong></section>'
        for label, value in fields
    )
    recent = payload.get("recent_statuses", [])
    transitions = payload.get("status_transitions", [])
    if not isinstance(recent, list) or not isinstance(transitions, list):
        raise ValueError("INVALID_HISTORY")
    if len(recent) > 10 or len(transitions) > 10:
        raise ValueError("HISTORY_LIMIT_EXCEEDED")
    def rows(items, transition=False):
        output = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("INVALID_HISTORY_ENTRY")
            time = _timestamp(item.get("timestamp_utc"))
            if transition:
                desc = _status(item.get("from")) + " → " + _status(item.get("to"))
            else:
                desc = _status(item.get("status"))
            output.append("<li><time>" + time + "</time><span>" +
                          html.escape(desc) + "</span></li>")
        return "".join(output) or "<li>No validated history available.</li>"
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>SPACE BAR AI | Local Status</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{font-family:system-ui,sans-serif;margin:0;background:#101724;color:#eaf1ff}
main{max-width:820px;margin:auto;padding:24px 16px}h1{font-size:1.5rem;margin-bottom:4px}
.sub{color:#adc0da}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px;margin:24px 0}
.card{background:#233249;border-radius:12px;padding:16px;overflow-wrap:anywhere}.label{color:#b8cbe8;font-size:.85rem;margin-bottom:8px}
strong{font-size:1.05rem}section.panel{background:#1b2739;padding:16px;border-radius:12px;margin:14px 0}
ul{list-style:none;padding:0}li{display:flex;justify-content:space-between;gap:14px;padding:12px 0;border-bottom:1px solid #34465c;overflow-wrap:anywhere}
time{color:#adc0da}footer{color:#f0c46d;margin-top:26px;font-size:.9rem}
</style></head><body><main>
<h1>SPACE BAR AI</h1><p class="sub">Offline diagnostic status • Snapshot generated: """ + _timestamp(payload.get("generated_utc")) + """</p>
<div class="cards">""" + cards + """</div>
<section class="panel"><h2>Recent diagnostic events</h2><ul>""" + rows(recent) + """</ul></section>
<section class="panel"><h2>Status transitions</h2><ul>""" + rows(transitions, True) + """</ul></section>
<footer>LOCAL FILE ONLY • RESEARCH ONLY • LIVE TRADING DISABLED</footer>
</main></body></html>
"""

def convert(source, destination):
    source = Path(source)
    if source.stat().st_size > MAX_BYTES:
        raise ValueError("STATUS_FILE_TOO_LARGE")
    payload = json.loads(source.read_text(encoding="utf-8"))
    page = render(payload)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".v88-", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(page)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination

def main():
    parser = argparse.ArgumentParser(description="Convert V87 local status JSON into mobile HTML")
    parser.add_argument("--input", type=Path, default=Path("reports/v87/mobile_status.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/v88/mobile_status.html"))
    args = parser.parse_args()
    try:
        output = convert(args.input, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("HTML report blocked:", type(exc).__name__)
        return 1
    print("SPACE BAR AI | OFFLINE MOBILE REPORT:", output)
    print("Open this local HTML file in a browser. No remote access or trading.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
