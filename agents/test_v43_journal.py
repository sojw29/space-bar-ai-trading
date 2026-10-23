"""V43 persistent paper journal tests. No exchange, no orders, no real accounts."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_journal_v43 import PaperJournal, verify_session, session_events, GENESIS


def paper_snapshot(cash=10000.0):
    return {"schema_version":"42.0","mode":"LOCAL_PAPER_SIMULATION",
            "paper_only":True,"orders_enabled":False,
            "live_trading_approved":False,"independent_oos_verified":False,
            "paper_cash":cash,"position":None,"state":"SIMULATING"}


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"paper"/"journal.sqlite3"
        self.journal=PaperJournal(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_persists_snapshots_across_instances_without_resuming(self):
        self.journal.append("paper_snapshot",paper_snapshot(10000))
        self.journal.append("paper_snapshot",paper_snapshot(9800))
        audit=verify_session(self.path,self.journal.session_id)
        self.assertEqual(audit["entries"],2)
        self.assertNotEqual(audit["last_hash"],GENESIS)
        logs=session_events(self.path,self.journal.session_id)
        self.assertEqual(logs[0]["paper_data"]["paper_cash"],9800)
        second=PaperJournal(self.path)
        self.assertNotEqual(second.session_id,self.journal.session_id)
        self.assertEqual(verify_session(self.path,second.session_id)["entries"],0)
        self.assertEqual(verify_session(self.path,self.journal.session_id)["entries"],2)

    def test_sqlite_tampering_detected(self):
        self.journal.append("paper_snapshot",paper_snapshot())
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE paper_events SET payload_json=? WHERE session_id=?",
                         ('{"paper_only":false}',self.journal.session_id))
        with self.assertRaisesRegex(ValueError,"digest mismatch"):
            verify_session(self.path,self.journal.session_id)
        with self.assertRaises(ValueError):
            session_events(self.path,self.journal.session_id)

    def test_rejects_unsafe_or_non_finite_records(self):
        snap=paper_snapshot()
        snap["orders_enabled"]=True
        with self.assertRaises(ValueError):
            self.journal.append("paper_snapshot",snap)
        snap=paper_snapshot()
        snap["paper_cash"]=float("nan")
        with self.assertRaises(ValueError):
            self.journal.append("paper_snapshot",snap)
        with self.assertRaises(ValueError):
            self.journal.append("real_order",paper_snapshot())
        self.assertEqual(verify_session(self.path,self.journal.session_id)["entries"],0)

    def test_multiple_session_independence(self):
        other=PaperJournal(self.path)
        self.journal.append("paper_snapshot",paper_snapshot())
        other.append("feed_halt",paper_snapshot(9700))
        self.assertEqual(verify_session(self.path,self.journal.session_id)["entries"],1)
        self.assertEqual(verify_session(self.path,other.session_id)["entries"],1)

    def test_limit_and_serialization(self):
        for n in range(3):
            self.journal.append("paper_snapshot",paper_snapshot(10000-n))
        self.assertEqual(len(session_events(self.path,self.journal.session_id,limit=2)),2)
        with self.assertRaises(ValueError):
            session_events(self.path,self.journal.session_id,limit=0)


if __name__=="__main__":
    unittest.main(verbosity=2)
