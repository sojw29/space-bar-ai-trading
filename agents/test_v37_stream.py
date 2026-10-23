"""V37 transport-free candle integrity regression tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from closed_candle_stream_v37 import ClosedCandleStream,StreamIntegrityError,replay_closed_history


BASE = 1700000100 - (1700000100 % 300)
NOW = BASE + 1000*300

def bar(i):
    p = 100+i*.1
    return {"timestamp":BASE+i*300,"open":p-.02,"high":p+.1,
            "low":p-.1,"close":p,"volume":20,"closed":True}


class CandleStreamTests(unittest.TestCase):
    def test_warmup_then_one_event_per_closed_bar(self):
        stream=ClosedCandleStream(now=lambda:NOW)
        for i in range(54):
            self.assertIsNone(stream.ingest(bar(i)))
        report=stream.ingest(bar(54))
        self.assertEqual(report["event_schema_version"],"27.0")
        self.assertEqual(len(report["events"]),7)
        self.assertFalse(report["orders_enabled"])
        self.assertFalse(stream.status["realtime_feed_connected"])
        self.assertEqual(stream.status["emissions"],1)

    def test_unclosed_and_future_rejected_without_mutation(self):
        stream=ClosedCandleStream(now=lambda:BASE+300)
        item=bar(0);item["closed"]=False
        with self.assertRaises(StreamIntegrityError):
            stream.ingest(item)
        with self.assertRaises(StreamIntegrityError):
            stream.ingest(bar(1))
        self.assertEqual(stream.status["buffered_bars"],0)

    def test_duplicate_and_out_of_order_do_not_change_state(self):
        stream=ClosedCandleStream(now=lambda:NOW)
        stream.ingest(bar(0));stream.ingest(bar(1))
        for item in (bar(1),bar(0)):
            with self.assertRaises(StreamIntegrityError):
                stream.ingest(item)
        self.assertEqual(stream.status["buffered_bars"],2)

    def test_gap_forces_warmup_restart(self):
        stream=ClosedCandleStream(now=lambda:NOW)
        for i in range(55):stream.ingest(bar(i))
        self.assertEqual(stream.status["emissions"],1)
        self.assertIsNone(stream.ingest(bar(56)))
        self.assertEqual(stream.status["gap_resets"],1)
        self.assertEqual(stream.status["buffered_bars"],1)
        for i in range(57,110):self.assertIsNone(stream.ingest(bar(i)))
        self.assertIsNotNone(stream.ingest(bar(110)))

    def test_invalid_ohlcv_and_alignment(self):
        stream=ClosedCandleStream(now=lambda:NOW)
        bad=bar(0);bad["volume"]=-3
        with self.assertRaises(StreamIntegrityError):stream.ingest(bad)
        bad=bar(0);bad["timestamp"]+=1
        with self.assertRaises(StreamIntegrityError):stream.ingest(bad)
        self.assertEqual(stream.status["buffered_bars"],0)

    def test_replay_is_historical_not_live(self):
        events,status=replay_closed_history([bar(i) for i in range(58)],now=lambda:NOW)
        self.assertEqual(len(events),4)
        self.assertFalse(status["realtime_feed_connected"])


if __name__=="__main__":
    unittest.main(verbosity=2)
