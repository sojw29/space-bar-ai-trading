"""V123 deterministic, offline Markdown/JSON walk-forward research report.

All reports are descriptive hypothetical backtests; no real orders.
"""
import argparse
import json
from pathlib import Path

from ema_signal_pipeline_v116 import read_history
from walkforward_selection_v120 import walkforward
from walkforward_scorecard_v121 import scorecard
from research_risk_warnings_v122 import audit

def build(rows,initial_train=300,test_bars=150,budget_fraction=0.05):
    wf=walkforward(rows,initial_train,test_bars,budget_fraction)
    summary=scorecard(wf)
    risk=audit(summary)
    return {
        "version":"V123.0","status":"OFFLINE_RESEARCH_REPORT",
        "configuration":{"initial_train":initial_train,"test_bars":test_bars,
                         "budget_fraction":budget_fraction},
        "scorecard":summary,"risk_audit":risk,
        "folds":[{"fold":f["fold"],"train_bars":f["train_bars"],
                  "train_end_timestamp":f["train_end_timestamp"],
                  "test_start_timestamp":f["test_start_timestamp"],
                  "test_end_timestamp":f["test_end_timestamp"],
                  "selected_strategy":f["selected_strategy"],
                  "validation":f["validation"]} for f in wf["folds"]],
        "simulation_only":True,"research_only":True,
        "exchange_connected":False,"orders_submitted_to_exchange":0,
        "live_trading_approved":False,"validated_edge":False,
        "limitations":"Hypothetical independent fold paper results only; no continuous compounded portfolio performance, real fills, spread or slippage. Warning absence does not constitute trading approval."
    }

def markdown(report):
    if not isinstance(report,dict) or report.get("version")!="V123.0":
        raise ValueError("INVALID_REPORT")
    s=report["scorecard"]
    a=report["risk_audit"]
    def fmt(value):
        return "N/A" if value is None else str(value)
    lines=[
        "# SPACE BAR AI TRADING — V123 Offline Research Report",
        "",
        "**RESEARCH ONLY · HYPOTHETICAL PAPER REPLAY · NO LIVE ORDERS**",
        "",
        "## Walk-Forward Scorecard",
        "",
        "| Metric | Value |","|---|---:|",
        f"| Total folds | {s['total_folds']} |",
        f"| Evaluated folds | {s['evaluated_folds']} |",
        f"| Abstained folds | {s['abstained_folds']} |",
        f"| Positive fold rate (%) | {fmt(s['positive_fold_rate_pct'])} |",
        f"| Mean fold return (%) | {fmt(s['mean_fold_return_pct'])} |",
        f"| Median fold return (%) | {fmt(s['median_fold_return_pct'])} |",
        f"| Worst fold return (%) | {fmt(s['worst_fold_return_pct'])} |",
        f"| Worst fold max drawdown (%) | {fmt(s['worst_fold_max_drawdown_pct'])} |",
        f"| Hypothetical closed sells | {s['hypothetical_sell_events']} |",
        f"| Strategy switches | {s['strategy_switch_count']} |",
        "",
        "## Risk Warnings","",
    ]
    if a["warnings"]:
        for warning in a["warnings"]:
            lines.append(f"- **{warning['code']}**: {warning['detail']}")
    else:
        lines.append("- No configured warnings triggered. **This is NOT approval.**")
    lines.extend(["","## Chronological Validation Folds","",
                  "| Fold | Selected strategy | Test start | Test end | Hypothetical return (%) | Max drawdown (%) |",
                  "|---:|---|---|---|---:|---:|"])
    for fold in report["folds"]:
        perf=fold["validation"]
        lines.append("| "+ " | ".join([
            str(fold["fold"]),fmt(fold["selected_strategy"]),
            str(fold["test_start_timestamp"]),str(fold["test_end_timestamp"]),
            fmt(perf["total_return_pct"]) if perf else "N/A",
            fmt(perf["max_drawdown_pct"]) if perf else "N/A"])+" |")
    lines.extend(["","## Limitations","",report["limitations"],"",
                  "**No exchange connection, no submitted orders, no validated edge.**",""])
    return "\n".join(lines)

def run(path,initial_train=300,test_bars=150,budget_fraction=0.05):
    return build(read_history(path),initial_train,test_bars,budget_fraction)

def main():
    parser=argparse.ArgumentParser(description="V123 offline JSON and Markdown research report")
    parser.add_argument("history_csv")
    parser.add_argument("--initial-train",type=int,default=300)
    parser.add_argument("--test-bars",type=int,default=150)
    parser.add_argument("--budget-fraction",type=float,default=0.05)
    parser.add_argument("--json-out",type=Path)
    parser.add_argument("--md-out",type=Path)
    args=parser.parse_args()
    report=run(args.history_csv,args.initial_train,args.test_bars,args.budget_fraction)
    if args.json_out:
        args.json_out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if args.md_out:
        args.md_out.write_text(markdown(report),encoding="utf-8")
    if not args.json_out and not args.md_out:
        print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
