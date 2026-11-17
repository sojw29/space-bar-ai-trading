"""Static regression checks for the isolated AI meeting UI script.

These checks prevent meeting-only logic from leaking into unrelated room panels.
"""
import re
import unittest
from pathlib import Path

ROOM = (Path(__file__).resolve().parent.parent / "web" / "office_3d.html").read_text(encoding="utf-8")


class MeetingPanelIsolationTests(unittest.TestCase):
    def test_meeting_script_is_isolated_from_indicator_panel(self):
        self.assertEqual(ROOM.count('id="ai-meeting-panel"'), 1)
        self.assertEqual(ROOM.count('id="ai-meeting-timeline"'), 1)
        before, after = ROOM.split("/* Completed model meeting snapshots only.", 1)
        self.assertNotIn("clearLinked()", before)
        self.assertNotIn("clearTimeline()", before)
        self.assertIn("function clearLinked()", after)
        self.assertIn("function clearTimeline()", after)

    def test_concern_comparison_is_conservative(self):
        meeting = ROOM.split("/* Completed model meeting snapshots only.", 1)[1]
        self.assertIn("const initialSet=new Set(initial.concerns)", meeting)
        self.assertIn("const reviewSet=new Set(review.concerns)", meeting)
        self.assertIn("initialSet.has(value)", meeting)
        self.assertIn("!initialSet.has(value)", meeting)
        self.assertIn("!reviewSet.has(value)", meeting)
        self.assertIn("재언급이 없다고 해결된 것은 아닙니다", meeting)

    def test_selection_and_expiry_cleanup(self):
        meeting = ROOM.split("/* Completed model meeting snapshots only.", 1)[1]
        self.assertIn('node.setAttribute?.("aria-pressed",active?"true":"false")', meeting)
        self.assertIn("markSelected(line)", meeting)
        self.assertIn("markSelected(conclusion)", meeting)
        self.assertGreaterEqual(meeting.count("clearLinked();clearTimeline();"), 2)
        self.assertIn("timeline.replaceChildren(...lines)", meeting)


if __name__ == "__main__":
    unittest.main()
