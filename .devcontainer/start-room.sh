#!/usr/bin/env bash
# Start a read-only local research dashboard for a PRIVATE Codespaces forwarded port.
set -euo pipefail
cd "$(dirname "$0")/.."
meeting_args=()
if (( $# )); then
  if [[ $# != 2 || $1 != --meeting-session || -z $2 ]]; then
    echo "Usage: bash .devcontainer/start-room.sh [--meeting-session SESSION_FOLDER]" >&2
    exit 2
  fi
  meeting_args=(--meeting-session "$2")
fi
if curl --silent --fail --max-time 2 http://127.0.0.1:8765/health >/dev/null; then
  if (( ${#meeting_args[@]} )); then
    echo "Port 8765 already has a server. Stop it before selecting a meeting session; the existing session was not changed." >&2
    exit 1
  fi
  echo "SPACE BAR research dashboard already running on 127.0.0.1:8765"
  exit 0
fi
if (( ${#meeting_args[@]} )); then
  echo "Starting the selected read-only meeting session in this terminal; Ctrl+C stops it."
  echo "Keep forwarded port 8765 PRIVATE; open its URL + /office3d."
  exec python -u agents/dashboard_api_v28.py --port 8765 "${meeting_args[@]}"
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
