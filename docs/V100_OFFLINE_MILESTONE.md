# SPACE BAR AI TRADING — V100 offline research milestone

V100 validates **local diagnostics, desktop environment prerequisites and offline
report generation**. It does **not** validate profitable strategies, autonomous
learning, reliable long-running paper trading or any live exchange order path.

## Windows quick start

1. Install Python 3.11 or 3.12 (with tkinter) and Git.
2. Clone the repository and open a terminal at its root.
3. Run `python agents/environment_preflight_v99.py` to check local prerequisites.
4. Run `python agents/integration_verifier_v98.py` for isolated report/alert tests.
5. Run `python agents/milestone_gate_v100.py` for the combined milestone gate.
6. Run `python agents/unified_launcher_v97.py` to open the desktop control
   center; use its Readiness, Alerts and Generate mobile report buttons.

For headless use, run `python agents/unified_launcher_v97.py --headless readiness`
or `--headless alerts`. Report generation produces local JSON and HTML files
under `reports/v97/`; transfer the HTML file manually to a phone to view it.
No remote status server is included.

## Interpreting results

- `OFFLINE_MILESTONE_PASS`: local environment and isolated offline
  reporting/diagnostic integration tests passed.
- `BLOCKED`: at least one prerequisite or integration test failed.
- Neither result grants permission to trade or indicates expected returns.

## Before considering live trading

Independently validate historical data integrity, out-of-sample strategy
performance and overfitting controls; run extended paper trading with
realistic fees, funding, slippage and order states; test duplicate orders,
partial fills, restarts, disconnections, stop failures, risk limits and
emergency shutdown; review API key permissions and secrets handling.
Do not activate real orders based on V100 status.

## Known limitations

Windows GUI interactions require manual testing on the user's own PC.
The milestone checks only the offline diagnostics/reporting subsystem,
not every historical strategy or agent. Mobile reports are local files,
not real-time monitoring. Autonomous AI learning and live trading are
not approved or validated.
