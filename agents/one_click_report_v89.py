"""V89 one-click offline status report generator (JSON + mobile HTML).

No network access, remote server, exchange orders or live trading.
"""
import argparse
import json
import threading
from pathlib import Path
from mobile_status_export_v87 import export
from mobile_html_report_v88 import convert

def generate(repo=None, reports=None, log=None, output_dir=None):
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parent.parent
    reports = Path(reports).resolve() if reports else repo / "reports"
    output_dir = Path(output_dir).resolve() if output_dir else reports / "v89"
    json_path = output_dir / "mobile_status.json"
    html_path = output_dir / "mobile_status.html"
    payload = export(json_path, repo=repo, reports=reports, log=log)
    convert(json_path, html_path)
    return {"version": "V89.0", "status": payload["overall_status"],
            "json_path": str(json_path), "html_path": str(html_path),
            "research_only": True, "live_trading_approved": False,
            "transport": "LOCAL_FILE_ONLY"}

def start_gui(repo=None, reports=None, log=None, output_dir=None):
    import tkinter as tk
    root = tk.Tk()
    root.title("SPACE BAR AI | Mobile Report Builder")
    root.geometry("650x290")
    root.configure(bg="#111927")
    tk.Label(root, text="SPACE BAR AI  |  MOBILE REPORT",
             font=("Segoe UI", 17, "bold"), bg="#111927", fg="#e9f0ff").pack(pady=18)
    state = tk.StringVar(value="Generate a local JSON + HTML status report.")
    tk.Label(root, textvariable=state, bg="#111927", fg="#c3d3ee",
             wraplength=600).pack(pady=12)
    def complete(result):
        if not root.winfo_exists():
            return
        state.set("Generated: " + result["html_path"] + "\nStatus: " + result["status"])
        button.configure(state="normal")
    def failed():
        if not root.winfo_exists():
            return
        state.set("Report generation failed. No network or trading action taken.")
        button.configure(state="normal")
    def run():
        button.configure(state="disabled")
        state.set("Generating offline report...")
        def worker():
            try:
                result = generate(repo, reports, log, output_dir)
            except Exception:
                root.after(0, failed)
            else:
                root.after(0, complete, result)
        threading.Thread(target=worker, daemon=True).start()
    button = tk.Button(root, text="Generate mobile report", command=run,
                       padx=24, pady=10, font=("Segoe UI", 12))
    button.pack(pady=14)
    tk.Label(root, text="LOCAL FILE ONLY  •  LIVE TRADING DISABLED",
             bg="#111927", fg="#f1c97b").pack(pady=10)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="One-click offline mobile status report")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    if args.headless:
        result = generate(args.repo, args.reports, args.log, args.output_dir)
        print(json.dumps(result, indent=2))
        return 1 if result["status"] == "BLOCKED" else 0
    try:
        start_gui(args.repo, args.reports, args.log, args.output_dir)
    except (ImportError, RuntimeError, OSError):
        print("GUI unavailable: use --headless.")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
