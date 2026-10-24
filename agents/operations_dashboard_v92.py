"""V92 offline desktop dashboard combining diagnostics and operation health."""
import argparse
import json
import threading
from pathlib import Path
from timeline_dashboard_v86 import dashboard_data
from operation_health_v91 import summarize

def combined_status(repo=None, reports=None, log=None, journal=None):
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parent.parent
    reports = Path(reports).resolve() if reports else repo / "reports"
    journal = Path(journal).resolve() if journal else reports / "v90" / "operations.jsonl"
    diagnostics = dashboard_data(repo=repo, reports=reports, log=log)
    operations = summarize(journal)
    overall = diagnostics["status"]
    if overall != "BLOCKED":
        if operations["status"] == "BLOCKED":
            overall = "BLOCKED"
        elif operations["status"] != "OPERATIONAL" and overall == "LOCAL_STATUS_PASS":
            overall = "REVIEW"
    return {"version": "V92.0", "status": overall, "diagnostics": diagnostics,
            "operations": operations, "research_only": True,
            "live_trading_approved": False}

def start_gui(repo=None, reports=None, log=None, journal=None):
    import tkinter as tk
    from tkinter import scrolledtext
    root = tk.Tk()
    root.title("SPACE BAR AI | Diagnostics + Operations")
    root.geometry("940x650")
    root.configure(bg="#111927")
    tk.Label(root, text="SPACE BAR AI | OPERATIONS CONTROL",
             font=("Segoe UI", 17, "bold"), bg="#111927", fg="#e9f0ff").pack(pady=16)
    state = tk.StringVar(value="Refresh to check local diagnostics and report operations.")
    tk.Label(root, textvariable=state, bg="#111927", fg="#c3d3ee").pack(pady=5)
    cards = tk.Frame(root, bg="#111927")
    cards.pack(pady=12)
    fields = {}
    for label in ("OVERALL", "DIAGNOSTICS", "OPERATIONS", "FAILURE STREAK"):
        frame = tk.Frame(cards, bg="#24344a", padx=12, pady=9)
        frame.pack(side="left", padx=6)
        tk.Label(frame, text=label, bg="#24344a", fg="#b9cbea").pack()
        value = tk.StringVar(value="NOT CHECKED")
        tk.Label(frame, textvariable=value, bg="#24344a", fg="#fff", width=17,
                 font=("Segoe UI", 10, "bold")).pack()
        fields[label] = value
    output = scrolledtext.ScrolledText(root, wrap="word", height=24)
    output.pack(fill="both", expand=True, padx=22, pady=10)
    def show(data):
        if not root.winfo_exists():
            return
        fields["OVERALL"].set(data["status"])
        fields["DIAGNOSTICS"].set(data["diagnostics"]["status"])
        fields["OPERATIONS"].set(data["operations"]["status"])
        fields["FAILURE STREAK"].set(str(data["operations"]["consecutive_failures"]))
        output.delete("1.0", tk.END)
        output.insert(tk.END, json.dumps(data, indent=2, ensure_ascii=False))
        state.set("Local checks complete. Live trading remains disabled.")
        refresh.configure(state="normal")
    def error():
        if not root.winfo_exists():
            return
        state.set("Local check failed; no trading action taken.")
        refresh.configure(state="normal")
    def refresh_now():
        refresh.configure(state="disabled")
        state.set("Running local read-only checks...")
        def worker():
            try:
                result = combined_status(repo, reports, log, journal)
            except Exception:
                root.after(0, error)
            else:
                root.after(0, show, result)
        threading.Thread(target=worker, daemon=True).start()
    refresh = tk.Button(root, text="Refresh all local checks",
                        command=refresh_now, padx=20, pady=8)
    refresh.pack(pady=8)
    tk.Label(root, text="RESEARCH ONLY | NO LIVE TRADING | NO NETWORK SERVER",
             bg="#111927", fg="#f1c97b").pack(pady=8)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Local diagnostics and operations dashboard")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    if args.headless:
        result = combined_status(args.repo, args.reports, args.log, args.journal)
        print(json.dumps(result, indent=2))
        return 1 if result["status"] != "LOCAL_STATUS_PASS" else 0
    try:
        start_gui(args.repo, args.reports, args.log, args.journal)
    except (ImportError, RuntimeError, OSError):
        print("GUI unavailable: use --headless.")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
