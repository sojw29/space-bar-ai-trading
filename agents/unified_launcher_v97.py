"""V97 unified offline launcher for local research operations.

No network server, exchange orders, or live trading controls.
"""
import argparse
import json
from pathlib import Path
from alerts_dashboard_v94 import dashboard_with_alerts
from local_readiness_v95 import assess
from one_click_report_v89 import generate

ACTIONS = ("readiness", "alerts", "report")

def execute(action, repo=None, reports=None, log=None, journal=None):
    if action not in ACTIONS:
        raise ValueError("UNKNOWN_ACTION")
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parent.parent
    reports = Path(reports).resolve() if reports else repo / "reports"
    if action == "readiness":
        result = assess(repo=repo, reports=reports, log=log, journal=journal)
        status = result["status"]
    elif action == "alerts":
        result = dashboard_with_alerts(repo=repo, reports=reports, log=log, journal=journal)
        status = result["severity"]
    else:
        result = generate(repo=repo, reports=reports, log=log,
                          output_dir=reports / "v97")
        status = result["status"]
    return {"version": "V97.0", "action": action, "status": status,
            "result": result, "research_only": True,
            "live_trading_approved": False, "transport": "LOCAL_ONLY"}

def start_gui(repo=None, reports=None, log=None, journal=None):
    import tkinter as tk
    from tkinter import scrolledtext
    import threading
    root = tk.Tk()
    root.title("SPACE BAR AI | Offline Control Center")
    root.geometry("900x650")
    root.configure(bg="#101724")
    tk.Label(root, text="SPACE BAR AI  |  OFFLINE CONTROL CENTER",
             font=("Segoe UI", 18, "bold"), bg="#101724", fg="#eef4ff").pack(pady=16)
    state = tk.StringVar(value="Select a local operation.")
    tk.Label(root, textvariable=state, bg="#101724", fg="#c3d4ee").pack(pady=5)
    output = scrolledtext.ScrolledText(root, wrap="word", height=29)
    output.pack(fill="both", expand=True, padx=20, pady=12)
    buttons = tk.Frame(root, bg="#101724")
    buttons.pack(pady=8)
    controls = []
    def finished(result):
        if not root.winfo_exists():
            return
        output.delete("1.0", tk.END)
        output.insert(tk.END, json.dumps(result, indent=2, ensure_ascii=False))
        state.set(result["action"] + ": " + result["status"])
        for control in controls:
            control.configure(state="normal")
    def failed():
        if not root.winfo_exists():
            return
        state.set("Local operation failed; no trading action taken.")
        for control in controls:
            control.configure(state="normal")
    def invoke(action):
        for control in controls:
            control.configure(state="disabled")
        state.set("Running " + action + "...")
        def worker():
            try:
                result = execute(action, repo, reports, log, journal)
            except Exception:
                root.after(0, failed)
            else:
                root.after(0, finished, result)
        threading.Thread(target=worker, daemon=True).start()
    for label, action in (("Readiness", "readiness"), ("Alerts", "alerts"),
                          ("Generate mobile report", "report")):
        button = tk.Button(buttons, text=label, command=lambda a=action: invoke(a),
                           padx=12, pady=8)
        button.pack(side="left", padx=8)
        controls.append(button)
    tk.Label(root, text="OFFLINE RESEARCH ONLY  |  LIVE TRADING DISABLED",
             bg="#101724", fg="#f0c46d").pack(pady=12)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Unified offline SPACE BAR AI launcher")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--headless", choices=ACTIONS)
    args = parser.parse_args()
    if args.headless:
        result = execute(args.headless, args.repo, args.reports, args.log, args.journal)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.headless == "readiness":
            return 0 if result["status"] == "LOCAL_REPORT_READY" else 1
        if args.headless == "alerts":
            return 1 if result["status"] == "CRITICAL" else 0
        return 1 if result["status"] == "BLOCKED" else 0
    try:
        start_gui(args.repo, args.reports, args.log, args.journal)
    except (ImportError, RuntimeError, OSError):
        print("GUI unavailable: use --headless readiness|alerts|report.")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
