"""V174 meeting state history contract."""
import unittest
from pathlib import Path


class MeetingHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_accessible_read_only_log(self):
        for value in ('id="v174-meeting-history"', 'role="log"', 'aria-label="회의 상태 기록"', 'history.replaceChildren()', 'row.textContent='):
            self.assertIn(value, self.html)

    def test_bounded_deduplicated_and_no_fabricated_history(self):
        for value in ('const historyEntries=[];', 'if(key===lastHistoryKey)return;', 'if(historyEntries.length>20)historyEntries.length=20;', 'new Date().toISOString()', 'logMeeting("WAIT",null);'):
            self.assertIn(value, self.html)

    def test_fail_closed_log(self):
        for value in ('logMeeting("BLOCKED · "+reason,null);', 'NO VERIFIED EVIDENCE', 'logMeeting("ATLAS VERIFIED · GUARDIAN CLEAR · COMMANDER WAIT",data.evidence&&data.evidence.sha256);'):
            self.assertIn(value, self.html)


if __name__ == "__main__":
    unittest.main()
