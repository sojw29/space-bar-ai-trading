"""V214 Wilson-score uncertainty bounds for observed holdout win rates.

Intervals describe binomial sampling uncertainty under simplifying assumptions.
They do not establish trade independence, stationarity, or live profitability.
"""
import math

Z95 = 1.959963984540054


def wilson_interval(wins, trades):
    if (type(trades) is not int or type(wins) is not int or
            trades < 0 or wins < 0 or wins > trades):
        raise ValueError("INVALID_WIN_LOSS_COUNTS")
    if trades == 0:
        return None
    p = wins / trades
    z2 = Z95 * Z95
    denominator = 1 + z2 / trades
    center = (p + z2 / (2 * trades)) / denominator
    margin = Z95 * math.sqrt(p * (1-p) / trades + z2 / (4 * trades * trades)) / denominator
    return [round(max(0, (center-margin)*100), 4),
            round(min(100, (center+margin)*100), 4)]


def attach_winrate_uncertainty(scorecard):
    if (not isinstance(scorecard, dict) or
            scorecard.get("version") != "V197.0" or
            scorecard.get("research_only") is not True or
            scorecard.get("orders_allowed") is not False or
            scorecard.get("live_trading_approved") is not False):
        raise ValueError("INVALID_OR_UNSAFE_SCORECARD")
    rows = scorecard.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("MISSING_SCORECARD_ROWS")
    results = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("INVALID_SCORECARD_ROW")
        name = row.get("strategy")
        n = row.get("holdout_trades")
        rate = row.get("holdout_win_rate_pct")
        if (not isinstance(name, str) or not name or
                type(n) is not int or n < 0 or n > 1_000_000 or
                type(rate) not in (int, float) or not math.isfinite(rate) or
                not 0 <= rate <= 100):
            raise ValueError("INVALID_HOLDOUT_WIN_RATE")
        implied_wins = n * rate / 100
        wins = round(implied_wins)
        # Scorecards round win rates; tolerate 0.01 percentage-point rounding only.
        if n and abs(100 * wins / n - rate) > 0.011:
            raise ValueError("INCONSISTENT_WIN_RATE_AND_TRADES")
        if not n and rate != 0:
            raise ValueError("NONZERO_WIN_RATE_WITHOUT_TRADES")
        results.append({
            "strategy": name, "holdout_trades": n,
            "inferred_wins_from_rounded_rate": wins,
            "reported_win_rate_pct": rate,
            "wilson_95_pct_interval": wilson_interval(wins, n),
            "status": "NO_TRADES" if n == 0 else "DESCRIPTIVE_INTERVAL_ONLY",
        })
    return {
        "version": "V214.0", "status": "DESCRIPTIVE_UNCERTAINTY_ONLY",
        "method": "WILSON_SCORE_95_PERCENT",
        "rows": results, "research_only": True, "orders_allowed": False,
        "live_trading_approved": False, "ranking_enabled": False,
        "strategy_selection_enabled": False,
        "limitations": [
            "Win counts inferred from rounded win rate; consistency checked.",
            "Wilson intervals assume independent Bernoulli trials, which correlated trades may violate.",
            "No correction for multiple comparisons, regime changes, selection bias, or slippage uncertainty.",
            "Intervals do not measure expected return, profitability, or deployment readiness.",
        ],
    }
