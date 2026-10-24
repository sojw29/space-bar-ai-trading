"""V86 offline dashboard: current status and validated diagnostic timeline."""
import argparse
import json
import threading
from pathlib import Path
from desktop_status_v84 import build_snapshot
from status_timeline_v85 import timeline

def dashboard_data(repo=None, reports=None, log=None, recent=12):
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parent.parent
    reports = Path(reports).resolve() if reports else repo / "reports"
    log = Path(log).resolve() if log else reports / "v76" / "diagnostics.jsonl"
    current = build_snapshot(repo=repo, reports=reports, log=log)
    history = timeline(log, recent=recent)
    status = current["status"]
    if status != "BLOCKED" and history["status"] != "ANALYZED":
        status = "REVIEW"
    return {"version": "V86.0", "status": status,
            "current": current, "timeline": history,
            "research_only": True, "live_trading_approved": False}

def start_gui(repo=None, reports=None, log=None):
    import tkinter as tk
    from tkinter import scrolledtext
    root = tk.Tk()
    root.title("SPACE BAR AI | Status & Timeline")
    root.geometry("950x650")
    root.configure(bg="#111927")
    tk.Label(root, text="SPACE BAR AI  |  STATUS & HISTORY",
             font=("Segoe UI", 17, "bold"), fg="#e9f0ff", bg="#111927").pack(pady=14)
    status = tk.StringVar(value="Press Refresh to inspect local research diagnostics.")
    tk.Label(root, textvariable=status, fg="#c3d3ee", bg="#111927").pack(pady=6)
    cards = tk.Frame(root, bg="#111927")
    cards.pack(pady=10)
    fields = {}
    for label in ("OVERALL", "PC", "AUDIT", "HISTORY"):
        frame = tk.Frame(cards, bg="#24344a", padx=10, pady=9)
        frame.pack(side="left", padx=7)
        tk.Label(frame, text=label, bg="#24344a", fg="#b9cbea").pack()
        value = tk.StringVar(value="NOT CHECKED")
        tk.Label(frame, textvariable=value, width=18, bg="#24344a",
                 fg="#ffffff", font=("Segoe UI", 10, "bold")).pack()
        fields[label] = value
    output = scrolledtext.ScrolledText(root, wrap="word", height=24)
    output.pack(fill="both", expand=True, padx=20, pady=10)
    def render(data):
        if not root.winfo_exists():
            return
        current = data["current"]
        fields["OVERALL"].set(data["status"])
        fields["PC"].set(current["pc_status"])
        fields["AUDIT"].set(current["audit_status"])
        fields["HISTORY"].set(data["timeline"]["status"])
        lines = ["RECENT DIAGNOSTIC EVENTS"]
        for event in data["timeline"]["events"]:
            lines.append(event["timestamp_utc"] + "  " + event["status"])
        lines.append("\nSTATUS TRANSITIONS")
        for change in data["timeline"]["transitions"]:
            lines.append(change["timestamp_utc"] + "  " + change["from"] + " -> " + change["to"])
        if data["timeline"]["issues"]:
            lines.append("\nHISTORY ISSUES: " + ", ".join(data["timeline"]["issues"]))
        lines.append("\nFULL LOCAL REPORT\n" + json.dumps(data["current"], indent=2))
        output.delete("1.0", tk.END)
        output.insert(tk.END, "\n".join(lines))
        status.set("Last checked (UTC): " + current["timestamp_utc"])
        refresh.configure(state="normal")
    def error():
        if not root.winfo_exists():
            return
        status.set("Diagnostic refresh failed; trading remains disabled.")
        refresh.configure(state="normal")
    def refresh_now():
        refresh.configure(state="disabled")
        status.set("Checking local diagnostics and history...")
        def worker():
            try:
                result = dashboard_data(repo, reports, log)
            except Exception:
                root.after(0, error)
            else:
                root.after(0, render, result)
        threading.Thread(target=worker, daemon=True).start()
    refresh = tk.Button(root, text="Refresh status & timeline", command=refresh_now,
                        padx=20, pady=8)
    refresh.pack(pady=8)
    tk.Label(root, text="RESEARCH ONLY  |  LIVE TRADING DISABLED",
             fg="#f1c97b", bg="#111927").pack(pady=7)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Offline status and history dashboard")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    if args.headless:
        result = dashboard_data(args.repo, args.reports, args.log)
        print(json.dumps(result, indent=2))
        return 1 if result["status"] == "BLOCKED" else 0
    try:
        start_gui(args.repo, args.reports, args.log)
    except (ImportError, RuntimeError, OSError):
        print("GUI unavailable: use --headless.")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
