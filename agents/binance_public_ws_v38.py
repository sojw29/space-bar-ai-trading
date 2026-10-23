"""V38 public Binance USD-M futures 5m kline WebSocket adapter.

Explicit opt-in read-only market data. No account, API keys, trading/orders.
A new V37 55-bar warmup is required after *every* disconnect/reconnect.
Output is JSONL to stdout, not a connected dashboard or persistent evidence.
"""
import argparse
import json
import sys
import time

from closed_candle_stream_v37 import ClosedCandleStream, StreamIntegrityError

# 2026 Binance USD-M separated Market stream endpoint; old root retired.
PUBLIC_KLINE_URL = "wss://fstream.binance.com/market/ws/btcusdt@kline_5m"
EXPECTED_STREAM = "btcusdt@kline_5m"
MAX_MESSAGE_BYTES = 65536


def parse_public_kline(message):
    """Parse public exchange market event; return closed candle or None.

    Reject malformed or misrouted closed messages instead of accepting data
    from another symbol, market, timeframe or without explicit finality.
    """
    if isinstance(message, bytes):
        if len(message) > MAX_MESSAGE_BYTES:
            raise ValueError("WebSocket message too large")
        message = message.decode("utf-8")
    if not isinstance(message, str) or len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("Invalid WebSocket message")
    payload = json.loads(message)
    if not isinstance(payload, dict):
        raise ValueError("Malformed WebSocket payload")
    if "stream" in payload:
        if payload["stream"] != EXPECTED_STREAM:
            raise ValueError("Unexpected combined market stream")
        payload = payload.get("data")
        if not isinstance(payload, dict):
            raise ValueError("Invalid combined stream envelope")
    # Some maintenance/control messages are not kline data.
    if payload.get("e") != "kline":
        return None
    if payload.get("s") != "BTCUSDT":
        raise ValueError("Unexpected symbol")
    k = payload.get("k")
    if not isinstance(k, dict) or k.get("s") != "BTCUSDT" or k.get("i") != "5m":
        raise ValueError("Unexpected kline metadata")
    if k.get("x") is not True:
        return None
    start_ms, close_ms = k.get("t"), k.get("T")
    if (isinstance(start_ms, bool) or not isinstance(start_ms, int)
            or isinstance(close_ms, bool) or not isinstance(close_ms, int)
            or start_ms < 0 or start_ms % 300000 != 0
            or close_ms != start_ms + 300000 - 1):
        raise ValueError("Invalid 5m candle times")
    try:
        candle = {
            "timestamp": start_ms // 1000,
            "open": float(k["o"]),
            "high": float(k["h"]),
            "low": float(k["l"]),
            "close": float(k["c"]),
            "volume": float(k["v"]),
            "closed": True,
        }
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid price/volume field") from exc
    return candle


def run_forever(*, connect=None, emit=None, sleep=None, max_attempts=None, bootstrap=None):
    """Process opt-in public messages. Connection exceptions force fresh warmup.

    `connect` is an injected websocket factory for offline tests. The
    default uses optional `websocket-client`, only on explicit CLI run.
    """
    if max_attempts is not None and (isinstance(max_attempts, bool)
                                    or not isinstance(max_attempts, int) or max_attempts < 1):
        raise ValueError("max_attempts must be a positive integer")
    if connect is None:
        try:
            from websocket import create_connection
        except ImportError as exc:
            raise RuntimeError("Install websocket-client for opt-in public streaming") from exc
        connect = lambda: create_connection(PUBLIC_KLINE_URL, timeout=25)
    emit = emit or (lambda data: print(json.dumps(data, ensure_ascii=False,
                                                  allow_nan=False), flush=True))
    sleep = sleep or time.sleep
    attempt = 0
    while max_attempts is None or attempt < max_attempts:
        attempt += 1
        stream = ClosedCandleStream()
        connection = None
        emit({"type": "feed_status", "state": "CONNECTING", "attempt": attempt,
              "paper_only": True, "orders_enabled": False})
        try:
            connection = connect()
            overlap = None
            if bootstrap is not None:
                # Opt-in V40 warmup is safe only after the socket is open.
                # An invalid/stale REST snapshot causes a full reconnect and
                # no previous candle or signal can survive.
                overlap = bootstrap(stream)
            emit({"type": "feed_status", "state": "WARMING_UP",
                  "buffered_bars": 0, "paper_only": True, "orders_enabled": False})
            while True:
                raw = connection.recv()
                if raw is None or raw == "":
                    raise ConnectionError("WebSocket closed")
                try:
                    candle = parse_public_kline(raw)
                    if candle is None:
                        continue
                    if overlap is not None and candle["timestamp"] <= overlap["timestamp"]:
                        if candle["timestamp"] == overlap["timestamp"]:
                            from public_warmup_v40 import compare_overlap
                            if not compare_overlap(candle, overlap):
                                raise ValueError("WS/REST last candle overlap conflict")
                        # Older closed updates are only ignored when the
                        # last candle overlap matches exactly. Older events
                        # are unsafe: reset rather than skip them.
                        else:
                            raise ValueError("WS delivered a candle older than REST warmup")
                        continue
                    previous_resets = stream.status["gap_resets"]
                    event = stream.ingest(candle)
                    if stream.status["gap_resets"] > previous_resets:
                        emit({"type": "feed_status", "state": "GAP_RESET",
                              "buffered_bars": stream.status["buffered_bars"],
                              "paper_only": True, "orders_enabled": False})
                    if event is not None:
                        emit({"type": "research_events",
                              "source": "public_binance_usdm_ws",
                              "realtime_transport": True,
                              "paper_only": True, "orders_enabled": False,
                              "payload": event,
                              "closed_candle": candle,
                              "market_candles": stream.recent_closed_candles(60)})
                except (ValueError, StreamIntegrityError) as exc:
                    # A malformed, duplicated, or out-of-order *closed*
                    # candle destroys continuity assurance.
                    emit({"type": "feed_status", "state": "INVALID_CANDLE_RESET",
                          "reason": type(exc).__name__, "paper_only": True,
                          "orders_enabled": False})
                    raise ConnectionError("Market stream integrity reset") from exc
        except (KeyboardInterrupt, SystemExit):
            emit({"type": "feed_status", "state": "STOPPED", "orders_enabled": False})
            return
        except Exception as exc:
            # Never retain/reuse a prior decision after connection failure.
            emit({"type": "feed_status", "state": "DISCONNECTED",
                  "reason": type(exc).__name__, "paper_only": True,
                  "orders_enabled": False})
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
        if max_attempts is not None and attempt >= max_attempts:
            break
        sleep(min(30, 2 ** min(attempt, 4)))


def main():
    parser = argparse.ArgumentParser(description="Opt-in, public, no-order BTC 5m WS feed")
    parser.add_argument("--max-attempts", type=int, default=None,
                        help="Optional number of connection attempts, otherwise reconnect")
    args = parser.parse_args()
    try:
        run_forever(max_attempts=args.max_attempts)
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
