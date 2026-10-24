"""V84 offline desktop status dashboard with on-demand refresh.

No web server, exchange connectivity, trading or automatic repair.
"""
import argparse
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from operator_launcher_v81 import launch
from diagnostic_trends_v77 import analyze

def build_snapshot(repo=None, reports=None, log=None, now=None):
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parent.parent
    reports = Path(reports).resolve() if reports else repo / "reports"
    log = Path(log).resolve() if log else reports / "v76" / "diagnostics.jsonl"
    now = now or datetime.now(timezone.utc)
    check = launch("pc-check", repo=repo, reports=reports)
    audit = launch("audit", repo=repo, reports=reports, log=log)
    trends = analyze(log)
    statuses = (check["status"], audit["status"])
    overall = "BLOCKED" if "BLOCKED" in statuses else "REVIEW" if any(
        status not in ("PC_READY", "LOCAL_AUDIT_PASS") for status in statuses
    ) else "LOCAL_STATUS_PASS"
    return {"version": "V84.0", "timestamp_utc": now.isoformat(),
            "status": overall, "pc_status": check["status"],
            "audit_status": audit["status"], "history_status": trends["status"],
            "history": trends, "research_only": True,
            "live_trading_approved": False,
            "note": "Dashboard reflects local research diagnostics only."}

def start_dashboard(repo=None, reports=None, log=None):
    import tkinter as tk
    from tkinter import scrolledtext
    root = tk.Tk()
    root.title("SPACE BAR AI | Local Status Dashboard")
    root.geometry("820x560")
    root.configure(bg="#111927")
    header = tk.Label(root, text="SPACE BAR AI  |  STATUS DASHBOARD",
                      font=("Segoe UI", 17, "bold"), fg="#e9f0ff", bg="#111927")
    header.pack(pady=15)
    state = tk.StringVar(value="Press Refresh to inspect local research status.")
    tk.Label(root, textvariable=state, fg="#bbd0f1", bg="#111927").pack()
    cards = tk.Frame(root, bg="#111927")
    cards.pack(pady=14)
    fields = {}
    for name in ("OVERALL", "PC", "AUDIT", "HISTORY"):
        frame = tk.Frame(cards, bg="#24344a", padx=12, pady=10)
        frame.pack(side="left", padx=7)
        tk.Label(frame, text=name, bg="#24344a", fg="#afc4e6").pack()
        value = tk.StringVar(value="NOT CHECKED")
        tk.Label(frame, textvariable=value, bg="#24344a", fg="#ffffff",
                 font=("Segoe UI", 11, "bold"), width=16).pack()
        fields[name] = value
    output = scrolledtext.ScrolledText(root, wrap="word", height=17)
    output.pack(fill="both", expand=True, padx=22, pady=10)
    def display(result):
        if not root.winfo_exists():
            return
        for key, field in (("OVERALL", "status"), ("PC", "pc_status"),
                           ("AUDIT", "audit_status"), ("HISTORY", "history_status")):
            fields[key].set(result[field])
        state.set("Last checked (UTC): " + result["timestamp_utc"])
        output.delete("1.0", tk.END)
        output.insert(tk.END, json.dumps(result, indent=2, ensure_ascii=False))
        refresh.configure(state="normal")
    def error():
        if not root.winfo_exists():
            return
        state.set("Refresh failed; no trading action was taken.")
        refresh.configure(state="normal")
    def refresh_now():
        refresh.configure(state="disabled")
        state.set("Checking offline diagnostics...")
        def worker():
            try:
                result = build_snapshot(repo, reports, log)
            except Exception:
                root.after(0, error)
            else:
                root.after(0, display, result)
        threading.Thread(target=worker, daemon=True).start()
    refresh = tk.Button(root, text="Refresh local status", command=refresh_now,
                        font=("Segoe UI", 11), padx=20, pady=8)
    refresh.pack(pady=8)
    tk.Label(root, text="RESEARCH ONLY  •  LIVE TRADING DISABLED",
             bg="#111927", fg="#f1c97b").pack(pady=6)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Offline desktop status dashboard")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    if args.headless:
        result = build_snapshot(args.repo, args.reports, args.log)
        print(json.dumps(result, indent=2))
        return 1 if result["status"] == "BLOCKED" else 0
    try:
        start_dashboard(args.repo, args.reports, args.log)
    except (ImportError, RuntimeError, OSError):
        print("GUI unavailable: use --headless.")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
