"""V41 stateful paper accounting and conservative safety contract tests."""
import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_events_v27 as events
from paper_portfolio_v41 import PaperPortfolio, PaperIntegrityError

BASE=1700000100-(1700000100%300)


def source():
    rows=[]
    for i in range(55):
        p=100+i*.25
        rows.append({"timestamp":BASE+i*300,"open":p-.03,
                     "high":p+.1,"low":p-.1,"close":p,"volume":20})
    return rows


def observation(i, close=110):
    ts=BASE+i*300
    candle={"timestamp":ts,"close":close,"closed":True}
    envelope=copy.deepcopy(events.analyze_and_emit(source()))
    timestamp=datetime.fromtimestamp(ts,timezone.utc).isoformat()
    envelope["observed_candle_utc"]=timestamp
    for item in envelope["events"]:
        item["observed_candle_utc"]=timestamp
    return candle,envelope


class PaperPortfolioTests(unittest.TestCase):
    def setUp(self):
        self.engine=PaperPortfolio(clock=lambda:1900000000)

    def test_entry_then_stop_has_costs_and_no_same_bar_reentry(self):
        first,signal=observation(54,close=110)
        report=self.engine.on_completed_candle(first,signal)
        self.assertEqual(report["position"]["side"],"LONG")
        self.assertLess(report["cash"],10000)
        second,signal=observation(55,close=108)
        report=self.engine.on_completed_candle(second,signal)
        self.assertIsNone(report["position"])
        self.assertEqual(report["trades"][-1]["reason"],"CLOSE_STOP_THRESHOLD")
        self.assertLess(report["cash"],10000)
        self.assertEqual([x["type"] for x in report["trades"]],["ENTRY","EXIT"])
        self.assertFalse(report["orders_enabled"])
        self.assertFalse(report["live_trading_approved"])

    def test_duplicate_or_gap_halts_without_orders(self):
        candle,signal=observation(54)
        self.engine.on_completed_candle(candle,signal)
        with self.assertRaises(PaperIntegrityError):
            self.engine.on_completed_candle(candle,signal)
        self.assertTrue(self.engine.halted)
        self.assertEqual(self.engine.halt_reason,"CANDLE_GAP_OR_DUPLICATE")

    def test_incomplete_and_mismatched_signal_halt(self):
        candle,signal=observation(54)
        candle["closed"]=False
        with self.assertRaises(PaperIntegrityError):
            self.engine.on_completed_candle(candle,signal)
        self.assertTrue(self.engine.halted)
        other=PaperPortfolio(clock=lambda:1900000000)
        candle,signal=observation(54)
        signal["observed_candle_utc"]=datetime.fromtimestamp(BASE+55*300,timezone.utc).isoformat()
        for item in signal["events"]:
            item["observed_candle_utc"]=signal["observed_candle_utc"]
        with self.assertRaises(PaperIntegrityError):
            other.on_completed_candle(candle,signal)
        self.assertEqual(other.halt_reason,"SIGNAL_CANDLE_MISMATCH")

    def test_risk_veto_prevents_new_position(self):
        candle,signal=observation(54)
        # Change all directional votes to WAIT, matching commander tallies.
        for item in signal["events"]:
            item["decision"]="WAIT"
            if item["agent_id"]=="COMMANDER":
                item.update(long_votes=0,short_votes=0,risk_veto=True)
        report=self.engine.on_completed_candle(candle,signal)
        self.assertIsNone(report["position"])
        self.assertEqual(report["trades"],[])

    def test_loss_guard_halts_after_adverse_exit(self):
        engine=PaperPortfolio(clock=lambda:1900000000,
                              allocation=.20, max_daily_loss_pct=.001)
        first,signal=observation(54,close=110)
        engine.on_completed_candle(first,signal)
        next_candle,next_signal=observation(55,close=108)
        report=engine.on_completed_candle(next_candle,next_signal)
        self.assertTrue(report["halted"])
        self.assertEqual(report["halt_reason"],"DAILY_LOSS_GUARD")
        with self.assertRaises(PaperIntegrityError):
            engine.on_completed_candle(*observation(56))

    def test_limits_and_no_position_aliasing(self):
        with self.assertRaises(ValueError):
            PaperPortfolio(allocation=1)
        with self.assertRaises(ValueError):
            PaperPortfolio(fee_bps=-1)
        candle,signal=observation(54)
        report=self.engine.on_completed_candle(candle,signal)
        report["position"]["side"]="SHORT"
        self.assertEqual(self.engine.position["side"],"LONG")


if __name__=="__main__":
    unittest.main(verbosity=2)
