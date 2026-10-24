"""V101 conservative research evidence gate for V61 hypothetical performance.

A PASS means evidence is structurally sufficient for further research,
not a profitable strategy, trading permission, or verified out-of-sample edge.
"""
import argparse
import json
import math
from paper_performance_v61 import report_historical_paper

def evaluate(report):
    if not isinstance(report, dict):
        raise ValueError("INVALID_REPORT")
    required = {
        "schema_version": "61.0",
        "mode": "DESCRIPTIVE_HISTORICAL_PAPER_PERFORMANCE",
        "source": "historical_csv_snapshot",
        "realtime": False, "paper_only": True, "orders_enabled": False,
        "live_trading_approved": False, "oos_validated": False,
        "independent_oos_verified": False,
    }
    if any(type(report.get(k)) is not type(v) or report[k] != v for k, v in required.items()):
        raise ValueError("UNSAFE_OR_UNSUPPORTED_REPORT")
    n = report.get("paper_closed_trades")
    min_n = report.get("performance_sample_minimum_closed_trades")
    sufficient = report.get("performance_sample_sufficient")
    if (type(n) is not int or n < 0 or type(min_n) is not int or min_n < 30
            or type(sufficient) is not bool or sufficient != (n >= min_n)):
        raise ValueError("INCONSISTENT_SAMPLE")
    drawdown = report.get("paper_max_observed_drawdown_pct")
    net = report.get("paper_realized_net")
    if (type(drawdown) not in (float, int) or not math.isfinite(drawdown)
            or drawdown < 0 or drawdown > 100 or
            type(net) not in (float, int) or not math.isfinite(net)):
        raise ValueError("INVALID_PERFORMANCE_VALUES")
    checks = [
        {"code": "CLOSED_TRADE_SAMPLE", "status": "PASS" if sufficient else "BLOCKED"},
        {"code": "INDEPENDENT_OUT_OF_SAMPLE", "status": "BLOCKED"},
        {"code": "FORWARD_PAPER_VALIDATION", "status": "BLOCKED"},
        {"code": "REAL_EXECUTION_VALIDATION", "status": "BLOCKED"},
    ]
    return {
        "version": "V101.0", "status": "EVIDENCE_INSUFFICIENT",
        "checks": checks, "closed_trades": n, "minimum_closed_trades": min_n,
        "observed_paper_net": net, "observed_drawdown_pct": drawdown,
        "research_only": True, "live_trading_approved": False,
        "orders_enabled": False, "strategy_profitable_verified": False,
        "note": "Historical hypothetical observations only; no independent OOS, forward or execution evidence."
    }

def main():
    parser = argparse.ArgumentParser(description="V101 conservative historical research evidence gate")
    parser.add_argument("--history", required=True, help="Local historical CSV snapshot")
    args = parser.parse_args()
    result = evaluate(report_historical_paper(args.history))
    print(json.dumps(result, indent=2))
    return 1  # Always insufficient for live deployment

if __name__ == "__main__":
    raise SystemExit(main())
