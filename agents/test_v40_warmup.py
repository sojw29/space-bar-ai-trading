"""V40 REST/WS warmup integration tests: injected data, absolutely no network."""
import json
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from closed_candle_stream_v37 import ClosedCandleStream
import public_warmup_v40 as warm
import binance_public_ws_v38 as ws


# Recent, *already completed* 5m window. Never use future test bars.
END = (int(time.time()) // 300 - 2) * 300
START = END - 54*300
NOW = END + 330


def klines(count=55, start=START, include_open=False):
    result = []
    for i in range(count):
        ts = (start + i*300)*1000
        p = 100 + i*.1
        result.append([ts,str(p-.01),str(p+.1),str(p-.1),
                       str(p),"20",ts+299999,"0",0,"0","0","0"])
    if include_open:
        ts = (start + count*300)*1000
        result.append([ts,"120","121","119","120","5",ts+299999])
    return result


def event(i, start=START, *, changed=False):
    t=(start+i*300)*1000
    p=100+i*.1
    return json.dumps({"e":"kline","s":"BTCUSDT",
        "k":{"t":t,"T":t+299999,"s":"BTCUSDT","i":"5m",
             "o":str(p-.01),"h":str(p+.1),"l":str(p-.1),
             "c":str(p+1 if changed else p),"v":"20","x":True}})


class FakeSocket:
    def __init__(self, payloads):
        self.payloads=iter(payloads)
        self.closed=False
    def recv(self):
        return next(self.payloads, None)
    def close(self):
        self.closed=True


class FastWarmupTests(unittest.TestCase):
    def test_exactly_closed_recent_history_and_overlap(self):
        rows = warm.parse_warmup(klines(include_open=True), now=NOW)
        self.assertEqual(len(rows),55)
        self.assertTrue(rows[-1]["closed"])
        stream=ClosedCandleStream(now=lambda:NOW)
        previous=warm.bootstrap_stream(stream,fetch=lambda:klines(),now=NOW)
        self.assertEqual(stream.status["buffered_bars"],55)
        self.assertTrue(warm.compare_overlap(ws.parse_public_kline(event(54)),previous))

    def test_reject_gap_duplicate_and_stale(self):
        rows=klines()
        rows[20][0]+=300000
        rows[20][6]+=300000
        with self.assertRaises(ValueError):warm.parse_warmup(rows,now=NOW)
        rows=klines()
        rows[21]=list(rows[20])
        with self.assertRaises(ValueError):warm.parse_warmup(rows,now=NOW)
        with self.assertRaises(ValueError):warm.parse_warmup(klines(),now=NOW+1000)

    def test_reject_incomplete_middle_or_insufficient(self):
        rows=klines(count=54)
        with self.assertRaises(ValueError):warm.parse_warmup(rows,now=NOW)
        rows=klines()
        rows[14][6]=rows[14][0]+123
        with self.assertRaises(ValueError):warm.parse_warmup(rows,now=NOW)
        rows=klines(include_open=True)
        with self.assertRaises(ValueError):warm.parse_warmup(rows,now=START+55*300-1)

    def test_ws_rest_consistent_overlap_emits_next_close(self):
        # Simulate REST 55 completed candles then same last WS message
        # and following candle, both with a fake stream clock.
        output=[]
        fake=FakeSocket([event(54),event(55)])
        def bootstrap(stream):
            stream._now=lambda:NOW+300
            return warm.bootstrap_stream(stream,fetch=lambda:klines(),now=NOW)
        ws.run_forever(connect=lambda:fake,emit=output.append,sleep=lambda _:None,
                       max_attempts=1,bootstrap=bootstrap)
        signals=[x for x in output if x["type"]=="research_events"]
        self.assertEqual(len(signals),1)
        self.assertFalse(signals[0]["orders_enabled"])
        self.assertTrue(fake.closed)

    def test_conflicting_overlap_is_fail_closed(self):
        output=[]
        fake=FakeSocket([event(54,changed=True)])
        def bootstrap(stream):
            stream._now=lambda:NOW
            return warm.bootstrap_stream(stream,fetch=lambda:klines(),now=NOW)
        ws.run_forever(connect=lambda:fake,emit=output.append,sleep=lambda _:None,
                       max_attempts=1,bootstrap=bootstrap)
        self.assertFalse(any(x["type"]=="research_events" for x in output))
        self.assertTrue(any(x.get("state")=="INVALID_CANDLE_RESET" for x in output))

    def test_bootstrap_failure_does_not_reuse_signal(self):
        output=[]
        fake=FakeSocket([event(55)])
        ws.run_forever(connect=lambda:fake,emit=output.append,sleep=lambda _:None,
                       max_attempts=1,bootstrap=lambda stream: (_ for _ in ()).throw(ValueError("stale")))
        self.assertFalse(any(x["type"]=="research_events" for x in output))
        self.assertTrue(any(x.get("state")=="DISCONNECTED" for x in output))


if __name__=="__main__":
    unittest.main(verbosity=2)
