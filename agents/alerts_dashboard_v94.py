"""V94 offline Tkinter dashboard with operational alert severity and guidance."""
import argparse
import json
import threading
from pathlib import Path
from operations_dashboard_v92 import combined_status
from operations_alerts_v93 import evaluate

def dashboard_with_alerts(repo=None, reports=None, log=None, journal=None):
    data = combined_status(repo=repo, reports=reports, log=log, journal=journal)
    alert_data = evaluate(data)
    return {"version": "V94.0", "status": data["status"],
            "severity": alert_data["severity"],
            "diagnostics": data["diagnostics"], "operations": data["operations"],
            "alerts": alert_data["alerts"], "research_only": True,
            "live_trading_approved": False, "auto_remediation": False}

def start_gui(repo=None, reports=None, log=None, journal=None):
    import tkinter as tk
    from tkinter import scrolledtext
    root = tk.Tk()
    root.title("SPACE BAR AI | Operational Alerts")
    root.geometry("980x700")
    root.configure(bg="#101724")
    tk.Label(root, text="SPACE BAR AI  |  OPERATIONS & ALERTS",
             font=("Segoe UI", 17, "bold"), bg="#101724", fg="#eaf1ff").pack(pady=16)
    state = tk.StringVar(value="Refresh to inspect local diagnostics and operational alerts.")
    tk.Label(root, textvariable=state, bg="#101724", fg="#c4d4ed").pack(pady=5)
    cards = tk.Frame(root, bg="#101724")
    cards.pack(pady=10)
    fields = {}
    for label in ("OVERALL", "ALERT LEVEL", "OPERATIONS", "FAILURE STREAK"):
        frame = tk.Frame(cards, bg="#253650", padx=12, pady=10)
        frame.pack(side="left", padx=6)
        tk.Label(frame, text=label, bg="#253650", fg="#b9cbea").pack()
        value = tk.StringVar(value="NOT CHECKED")
        tk.Label(frame, textvariable=value, width=18, bg="#253650",
                 fg="#fff", font=("Segoe UI", 10, "bold")).pack()
        fields[label] = value
    output = scrolledtext.ScrolledText(root, wrap="word", height=25)
    output.pack(fill="both", expand=True, padx=20, pady=10)
    def render(data):
        if not root.winfo_exists():
            return
        fields["OVERALL"].set(data["status"])
        fields["ALERT LEVEL"].set(data["severity"])
        fields["OPERATIONS"].set(data["operations"]["status"])
        fields["FAILURE STREAK"].set(str(data["operations"]["consecutive_failures"]))
        lines = ["LOCAL OPERATIONAL ALERTS", ""]
        for alert in data["alerts"]:
            lines.extend(["[" + alert["level"] + "] " + alert["code"],
                          alert["message"], "Suggested check: " + alert["suggested_action"], ""])
        lines.extend(["", "LOCAL DIAGNOSTICS AND HISTORY", json.dumps(data["diagnostics"], indent=2)])
        output.delete("1.0", tk.END)
        output.insert(tk.END, "\n".join(lines))
        state.set("Local check completed. This is not approval for live trading.")
        refresh.configure(state="normal")
    def fail():
        if not root.winfo_exists():
            return
        state.set("Local check failed. No trading or automatic repairs were performed.")
        refresh.configure(state="normal")
    def refresh_now():
        refresh.configure(state="disabled")
        state.set("Checking offline status and alerts...")
        def worker():
            try:
                data = dashboard_with_alerts(repo, reports, log, journal)
            except Exception:
                root.after(0, fail)
            else:
                root.after(0, render, data)
        threading.Thread(target=worker, daemon=True).start()
    refresh = tk.Button(root, text="Refresh status & alerts", command=refresh_now,
                        padx=20, pady=8)
    refresh.pack(pady=9)
    tk.Label(root, text="RESEARCH ONLY | NO AUTOMATIC REPAIRS | LIVE TRADING DISABLED",
             bg="#101724", fg="#f0c46d").pack(pady=8)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Offline operations alert dashboard")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    if args.headless:
        result = dashboard_with_alerts(args.repo, args.reports, args.log, args.journal)
        print(json.dumps(result, indent=2))
        return 1 if result["severity"] == "CRITICAL" else 0
    try:
        start_gui(args.repo, args.reports, args.log, args.journal)
    except (ImportError, RuntimeError, OSError):
        print("GUI unavailable: use --headless.")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
