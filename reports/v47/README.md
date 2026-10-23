# V47 — Interactive 2.5D agent office

V47 polishes the SPACE BAR command center into a responsive **CSS-based 2.5D isometric research office**. Each of the seven deterministic rule-based agents (ATLAS, ORBIT, ECHO, PULSE, QUANT, APEX and COMMANDER) occupies a labelled desk with a small CSS avatar, market-decision-colored monitor and research activity tag. COMMANDER has a highlighted central desk. This is **not a true 3D engine**, an AI simulation of characters, or a demonstration of learned trading intelligence.

Choose a desk or agent card by clicking/tapping or using Enter/Space from keyboard focus to inspect the selected agent's most recent **research-only** decision, reason, data time, subjective confidence (when present) and consensus risk-veto details. A dedicated office spotlight echoes the selected agent's current research status. The room has a legend for LONG, SHORT and WAIT, is responsive on phone-sized displays, and honors reduced-motion preferences.

All decorations use local HTML/CSS; there are no external media imports. A disconnected, invalid or unavailable feed clears previous research decisions, resets desks and inspector to WAIT/unavailable and removes apparently active status; the optional V42 paper portfolio panel remains strictly separate, simulated-only and never activates orders.

### Run locally

From the repository root:

```bash
python agents/dashboard_api_v28.py --history data/history/BTC_5m.csv --port 8765
```

Then on the **same PC** open `http://127.0.0.1:8765/`. Historical CSV data must already exist; this command does not download it.

For optional public-market feed visualization, the existing V39/V40 server can be run with the optional `websocket-client` dependency. Its deployment and independent connectivity are **not** verified here.

### Safety and limits

This update is **UI-only**. It adds no market strategy, proof of profitability, independent forward evaluation, machine learning, exchange keys, order endpoints, real orders or automatic execution. It is not an actual WebGL 3D office or continuously running cloud website. CI uses offline static interface checks, JavaScript syntax validation and prior read-only backend test contracts.
