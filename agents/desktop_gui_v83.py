"""V83 local Tkinter desktop diagnostics UI. No network or trade actions."""
import argparse
import json
import threading
from pathlib import Path
from operator_launcher_v81 import launch

ACTIONS = (("PC readiness", "pc-check"),
           ("Integrated local audit", "audit"),
           ("Offline self-test", "self-test"))

def run_action(action, repo=None):
    if action not in {value for _, value in ACTIONS}:
        raise ValueError("ACTION_NOT_ALLOWED")
    result = launch(action, repo=repo)
    return {"version": "V83.0", "action": action,
            "status": result["status"], "details": result,
            "research_only": True, "live_trading_approved": False}

def start_gui(repo=None):
    # Lazy import allows CLI and unit tests on headless CI runners.
    import tkinter as tk
    from tkinter import scrolledtext
    root = tk.Tk()
    root.title("SPACE BAR AI | Offline Diagnostics")
    root.geometry("720x510")
    root.configure(bg="#101722")
    heading = tk.Label(root, text="SPACE BAR AI  •  LOCAL DIAGNOSTICS",
                       font=("Segoe UI", 16, "bold"), fg="#eaf1ff", bg="#101722")
    heading.pack(pady=16)
    state = tk.StringVar(value="Select a diagnostic action. Trading is disabled.")
    tk.Label(root, textvariable=state, fg="#b4c7e7", bg="#101722").pack(pady=4)
    output = scrolledtext.ScrolledText(root, height=18, wrap="word")
    output.pack(fill="both", expand=True, padx=20, pady=12)
    buttons = []

    def show_result(result):
        if not root.winfo_exists():
            return
        output.delete("1.0", tk.END)
        output.insert(tk.END, json.dumps(result, indent=2, ensure_ascii=False))
        state.set("Status: " + result["status"] + " | Live trading: DISABLED")
        for button in buttons:
            button.configure(state="normal")

    def on_error(message):
        if not root.winfo_exists():
            return
        state.set("Diagnostic failed. Trading remains disabled.")
        output.delete("1.0", tk.END)
        output.insert(tk.END, message)
        for button in buttons:
            button.configure(state="normal")

    def start(action):
        for button in buttons:
            button.configure(state="disabled")
        state.set("Running " + action + " ...")
        def worker():
            try:
                result = run_action(action, repo=repo)
            except Exception as exc:
                # Do not expose potentially sensitive exception details in GUI.
                root.after(0, on_error, type(exc).__name__)
            else:
                root.after(0, show_result, result)
        threading.Thread(target=worker, daemon=True).start()

    row = tk.Frame(root, bg="#101722")
    row.pack(pady=8)
    for label, action in ACTIONS:
        button = tk.Button(row, text=label, command=lambda a=action: start(a),
                           width=21, padx=5, pady=8)
        button.pack(side="left", padx=6)
        buttons.append(button)
    tk.Label(root, text="RESEARCH ONLY  |  NO EXCHANGE ORDERS",
             fg="#f3c66a", bg="#101722").pack(pady=9)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Local offline diagnostic GUI")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--headless", choices=[action for _, action in ACTIONS],
                        help="Run diagnostics without opening a window")
    args = parser.parse_args()
    if args.headless:
        result = run_action(args.headless, args.repo)
        print(json.dumps(result, indent=2))
        return 1 if result["status"] in ("BLOCKED", "FAIL") else 0
    try:
        start_gui(args.repo)
    except (ImportError, RuntimeError, OSError):
        print("GUI unavailable: use --headless or V82 terminal menu.")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
