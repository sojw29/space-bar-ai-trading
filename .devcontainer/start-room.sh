#!/usr/bin/env bash
# Start a read-only local research dashboard for a PRIVATE Codespaces forwarded port.
set -euo pipefail
cd "$(dirname "$0")/.."
if curl --silent --fail --max-time 2 http://127.0.0.1:8765/health >/dev/null; then
  echo "SPACE BAR research dashboard already running on 127.0.0.1:8765"
  exit 0
fi
nohup python -u agents/dashboard_api_v28.py --port 8765 > /tmp/space-bar-room.log 2>&1 < /dev/null &
pid=$!
sleep 2
if ! kill -0 "$pid" 2>/dev/null || ! curl --silent --fail --max-time 2 http://127.0.0.1:8765/health >/dev/null; then
  echo "SPACE BAR failed to start. Check /tmp/space-bar-room.log" >&2
  cat /tmp/space-bar-room.log >&2 || true
  exit 1
fi
echo "SPACE BAR read-only dashboard started (PID $pid)."
echo "In Codespaces PORTS tab keep port 8765 PRIVATE; open forwarded URL + /office3d."
echo "Historical analysis needs data/history/BTC_5m.csv; missing data must remain unavailable."
