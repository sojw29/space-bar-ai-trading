"""V46 fault-injection checks for production feed dispatcher.

No external network, trading API or real account.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_dashboard_v39 import LiveResearchStore, dispatch_feed_event
from paper_monitor_v42 import LocalPaperMonitor


class BrokenJournal:
    def append(self, kind, payload):
        raise OSError("simulated disk full")


class DispatchFailureTests(unittest.TestCase):
    def test_journal_io_failure_halts_paper(self):
        clock=lambda: 2000000000
        store=LiveResearchStore(clock=clock)
        paper=LocalPaperMonitor(clock=clock)
        # A warmup feed_status doesn't attempt to write journal.
        dispatch_feed_event(store,paper,BrokenJournal(),
            {"type":"feed_status","state":"WARMING_UP","orders_enabled":False})
        self.assertEqual(paper.snapshot()["state"],"WARMING_UP")
        # A disconnect MUST be persisted; injected disk fault must fail closed.
        with self.assertRaises(OSError):
            dispatch_feed_event(store,paper,BrokenJournal(),
                {"type":"feed_status","state":"DISCONNECTED","orders_enabled":False})
        snap=paper.snapshot()
        self.assertEqual(snap["state"],"HALTED")
        self.assertEqual(snap["halt_reason"],"PAPER_JOURNAL_OR_FEED_FAILURE")
        self.assertIsNone(snap["paper_mark_to_close_equity"])
        self.assertFalse(snap["orders_enabled"])

    def test_unsafe_research_state_cannot_activate_paper(self):
        store=LiveResearchStore()
        paper=LocalPaperMonitor()
        with self.assertRaises(ValueError):
            dispatch_feed_event(store,paper,None,
                {"type":"research_events","paper_only":False,
                 "orders_enabled":True,"payload":{}})
        self.assertEqual(paper.snapshot()["state"],"HALTED")
        self.assertIsNone(paper.snapshot()["position"])

    def test_feed_disconnect_cannot_be_undone_by_reconnect_status(self):
        store=LiveResearchStore()
        paper=LocalPaperMonitor()
        dispatch_feed_event(store,paper,None,
            {"type":"feed_status","state":"DISCONNECTED","orders_enabled":False})
        dispatch_feed_event(store,paper,None,
            {"type":"feed_status","state":"WARMING_UP","orders_enabled":False})
        self.assertEqual(paper.snapshot()["state"],"HALTED")
        self.assertIsNone(paper.snapshot()["position"])

if __name__=="__main__":
    unittest.main(verbosity=2)
