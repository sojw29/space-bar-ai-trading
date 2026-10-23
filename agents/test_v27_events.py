"""V27 UI event protocol contract tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import multi_agent_v26 as v26
import agent_events_v27 as v27


def sample():
    candles = []
    for i in range(60):
        p = 100 + i * 0.1
        candles.append({"timestamp": 1700000100 + i * 300, "open": p-0.01,
                        "high": p+0.1, "low": p-0.1, "close": p, "volume": 20})
    return candles


class EventContractTests(unittest.TestCase):
    def test_ui_events(self):
        report = v27.analyze_and_emit(sample())
        self.assertEqual(len(report["events"]), 7)
        self.assertEqual(report["events"][-1]["agent_id"], "COMMANDER")
        self.assertEqual({x["agent_id"] for x in report["events"]},
                         set(v26.AGENTS) | {"COMMANDER"})
        self.assertFalse(report["orders_enabled"])
        self.assertFalse(report["live_trading_approved"])
        self.assertEqual(report, v27.analyze_and_emit(sample()))

    def test_rejects_unsafe_flag(self):
        report = v26.analyze(sample())
        report["orders_enabled"] = True
        with self.assertRaises(ValueError):
            v27.events_for_analysis(report)

    def test_rejects_missing_agent(self):
        report = v26.analyze(sample())
        report["agents"].pop()
        with self.assertRaises(ValueError):
            v27.events_for_analysis(report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
