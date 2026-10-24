"""V82 keyboard-driven offline operator menu. No shell or trade actions."""
import argparse
import json
from operator_launcher_v81 import launch

MENU = {"1": ("PC readiness", "pc-check"),
        "2": ("Integrated local audit", "audit"),
        "3": ("Offline integration self-test", "self-test"),
        "0": ("Exit", None)}

def choose(selection, repo=None, reports=None, log=None):
    if selection not in MENU:
        return {"status": "INVALID_SELECTION", "live_trading_approved": False}
    label, action = MENU[selection]
    if action is None:
        return {"status": "EXIT", "live_trading_approved": False}
    result = launch(action, repo=repo, reports=reports, log=log if action == "audit" else None)
    return {"status": result["status"], "selection": selection,
            "label": label, "details": result,
            "live_trading_approved": False}

def run_menu(input_fn=input, output_fn=print, repo=None, reports=None, log=None):
    while True:
        output_fn("\nSPACE BAR AI | OFFLINE OPERATOR MENU")
        for key, (label, _) in MENU.items():
            output_fn(key + ". " + label)
        try:
            selection = input_fn("Choose: ").strip()
        except (EOFError, KeyboardInterrupt):
            output_fn("\nMenu closed.")
            return 0
        result = choose(selection, repo=repo, reports=reports, log=log)
        if result["status"] == "EXIT":
            output_fn("Menu closed.")
            return 0
        if result["status"] == "INVALID_SELECTION":
            output_fn("Invalid selection; choose 0-3.")
            continue
        output_fn("Result: " + result["status"])
        output_fn("Live trading: DISABLED")

def main():
    parser = argparse.ArgumentParser(description="Offline interactive operator menu")
    parser.add_argument("--once", choices=MENU.keys(), help="Run a single menu action non-interactively")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo")
    parser.add_argument("--reports")
    parser.add_argument("--log")
    args = parser.parse_args()
    if args.once is None:
        if args.json:
            parser.error("--json requires --once")
        return run_menu(repo=args.repo, reports=args.reports, log=args.log)
    result = choose(args.once, repo=args.repo, reports=args.reports, log=args.log)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("SPACE BAR AI | MENU RESULT:", result["status"])
        print("Live trading: DISABLED")
    return 1 if result["status"] in ("BLOCKED", "FAIL", "INVALID_SELECTION") else 0

if __name__ == "__main__":
    raise SystemExit(main())
