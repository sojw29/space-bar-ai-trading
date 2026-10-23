"""V38 offline adapter tests. No internet, account or websocket dependency."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import binance_public_ws_v38 as v38


START = 1700000100 - 1700000100 % 300


def message(index, *, closed=True, symbol="BTCUSDT", interval="5m"):
    t = (START + index*300)*1000
    p = 100 + index*.1
    return json.dumps({
        "e": "kline", "s": symbol,
        "k": {"t":t,"T":t+299999,"s":symbol,"i":interval,
              "o":str(p-.01),"h":str(p+.1),"l":str(p-.1),
              "c":str(p),"v":"20","x":closed},
    })


class FakeSocket:
    def __init__(self, payloads):
        self.messages = iter(payloads)
        self.closed = False

    def recv(self):
        try:
            return next(self.messages)
        except StopIteration:
            return None

    def close(self):
        self.closed = True


class BinanceParserTests(unittest.TestCase):
    def test_finality_and_symbol(self):
        self.assertIsNone(v38.parse_public_kline(message(0,closed=False)))
        candle = v38.parse_public_kline(message(0))
        self.assertTrue(candle["closed"])
        self.assertEqual(candle["timestamp"], START)
        with self.assertRaises(ValueError):
            v38.parse_public_kline(message(0,symbol="ETHUSDT"))
        with self.assertRaises(ValueError):
            v38.parse_public_kline(message(0,interval="15m"))

    def test_combined_stream_validation(self):
        raw = message(0)
        self.assertIsNotNone(v38.parse_public_kline(json.dumps(
            {"stream":v38.EXPECTED_STREAM,"data":json.loads(raw)})))
        with self.assertRaises(ValueError):
            v38.parse_public_kline(json.dumps(
                {"stream":"ethusdt@kline_5m","data":json.loads(raw)}))

    def test_reconnect_disallows_old_buffer(self):
        sockets = [FakeSocket([message(i) for i in range(54)]),
                   FakeSocket([message(i) for i in range(54,60)])]
        output = []
        v38.run_forever(connect=lambda:sockets.pop(0), emit=output.append,
                        sleep=lambda _:None, max_attempts=2)
        self.assertFalse(any(x["type"]=="research_events" for x in output))
        self.assertEqual(sum(x.get("state")=="DISCONNECTED" for x in output),2)

    def test_full_warmup_emits_research_only(self):
        sock = FakeSocket([message(i) for i in range(55)])
        output=[]
        v38.run_forever(connect=lambda:sock,emit=output.append,
                        max_attempts=1,sleep=lambda _:None)
        signals=[x for x in output if x["type"]=="research_events"]
        self.assertEqual(len(signals),1)
        self.assertFalse(signals[0]["orders_enabled"])
        self.assertFalse(signals[0]["payload"]["live_trading_approved"])
        self.assertTrue(sock.closed)

    def test_gap_clears_buffer_and_emits_status(self):
        sock = FakeSocket([message(i) for i in range(54)] + [message(55)])
        output=[]
        v38.run_forever(connect=lambda:sock,emit=output.append,
                        max_attempts=1,sleep=lambda _:None)
        self.assertTrue(any(x.get("state")=="GAP_RESET" for x in output))
        self.assertFalse(any(x["type"]=="research_events" for x in output))

    def test_invalid_closed_candle_resets(self):
        sock = FakeSocket([message(0),message(0)])
        output=[]
        v38.run_forever(connect=lambda:sock,emit=output.append,
                        max_attempts=1,sleep=lambda _:None)
        self.assertTrue(any(x.get("state")=="INVALID_CANDLE_RESET" for x in output))


if __name__ == "__main__":
    unittest.main(verbosity=2)
