# iPhone-only development: private GitHub Codespaces

This is a **development preview**, not a hosted 24/7 trading service. It exposes a read-only research UI via a **private** Codespaces forwarded port. The Python server binds only to 127.0.0.1:8765, not 0.0.0.0.

1. On iPhone Safari, sign in to GitHub and open the repository's **Code → Codespaces → Create codespace** menu. Select branch `feature/testnet-order-guard-20261104` **before creating** the codespace so the devcontainer files are included. GitHub may require enabling Codespaces or an available usage allowance.
2. Wait for the container to build. The `postStartCommand` starts the read-only server automatically. If it does not start, open a Codespaces terminal and run `bash .devcontainer/start-room.sh`.
3. In the Codespaces **PORTS** tab, locate port **8765**. Check that its **Port Visibility** is **Private**. **Never set it Public**. Open the forwarded URL in Safari, then append `/office3d` for the 3D room, `/dashboard` for the lightweight dashboard, or `/health` to check server status.
4. A missing historical dataset means `/api/v1/agents` will return **503** rather than fabricated data. Provide a valid CSV at `data/history/BTC_5m.csv` with columns `timestamp,open,high,low,close,volume` and completed contiguous BTC 5m candles if you want historical analysis. The 3D page loads Three.js from a CDN and requires WebGL; Safari support may vary.
5. For troubleshooting, in terminal run `cat /tmp/space-bar-room.log`, `curl -i http://127.0.0.1:8765/health`, or `bash .devcontainer/start-room.sh`.
6. Stop the Codespace from GitHub when not using it to control usage. Codespaces can suspend on idle and may incur charges; reconnect/restart it to continue. Do not put exchange secrets in repository, terminal logs, or screenshots.

Safety: This path starts `agents/dashboard_api_v28.py` only. It does **not** enable exchange credentials, AI provider inference, testnet orders, or live orders. A meeting transcript is displayed only when a valid completed snapshot is available. The private forwarded URL still requires access control; do not share it.
