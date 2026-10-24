"""V96 desktop readiness dashboard for offline local reporting only."""
import argparse
import json
import threading
from pathlib import Path
from local_readiness_v95 import assess

def readiness_view(repo=None, reports=None, log=None, journal=None):
    result = assess(repo=repo, reports=reports, log=log, journal=journal)
    return {"version": "V96.0", "status": result["status"],
            "passed": result["passed"], "total": result["total"],
            "checks": result["checks"], "research_only": True,
            "live_trading_approved": False, "scope": "LOCAL_REPORTING_ONLY"}

def start_gui(repo=None, reports=None, log=None, journal=None):
    import tkinter as tk
    root = tk.Tk()
    root.title("SPACE BAR AI | Local Readiness")
    root.geometry("900x600")
    root.configure(bg="#101724")
    tk.Label(root, text="SPACE BAR AI  |  LOCAL READINESS",
             font=("Segoe UI", 18, "bold"), bg="#101724", fg="#edf4ff").pack(pady=18)
    summary = tk.StringVar(value="Click Refresh to run local readiness checks.")
    tk.Label(root, textvariable=summary, bg="#101724", fg="#c3d4ee",
             font=("Segoe UI", 12)).pack(pady=6)
    body = tk.Frame(root, bg="#101724")
    body.pack(fill="both", expand=True, padx=24, pady=16)
    rows = []
    for index in range(5):
        line = tk.Frame(body, bg="#22334c", padx=14, pady=11)
        line.pack(fill="x", pady=5)
        label = tk.StringVar(value="Waiting for check...")
        tk.Label(line, textvariable=label, bg="#22334c", fg="#f2f6ff",
                 anchor="w", font=("Segoe UI", 11)).pack(fill="x")
        rows.append(label)
    def show(result):
        if not root.winfo_exists():
            return
        summary.set(result["status"] + "  |  " + str(result["passed"]) + "/" +
                    str(result["total"]) + " local checks passed")
        for field, check in zip(rows, result["checks"]):
            field.set(check["status"] + "  |  " + check["code"] + "  —  " + check["detail"])
        refresh.configure(state="normal")
    def failed():
        if not root.winfo_exists():
            return
        summary.set("BLOCKED — local readiness check could not finish.")
        refresh.configure(state="normal")
    def refresh_now():
        refresh.configure(state="disabled")
        summary.set("Running local readiness checks...")
        def worker():
            try:
                data = readiness_view(repo, reports, log, journal)
            except Exception:
                root.after(0, failed)
            else:
                root.after(0, show, data)
        threading.Thread(target=worker, daemon=True).start()
    refresh = tk.Button(root, text="Refresh readiness", command=refresh_now,
                        padx=24, pady=10, font=("Segoe UI", 11))
    refresh.pack(pady=8)
    tk.Label(root, text="LOCAL REPORTING ONLY  |  NO LIVE TRADING APPROVAL",
             bg="#101724", fg="#f0c46d").pack(pady=12)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Offline local readiness desktop dashboard")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    if args.headless:
        result = readiness_view(args.repo, args.reports, args.log, args.journal)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "LOCAL_REPORT_READY" else 1
    try:
        start_gui(args.repo, args.reports, args.log, args.journal)
    except (ImportError, RuntimeError, OSError):
        print("GUI unavailable: use --headless.")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
