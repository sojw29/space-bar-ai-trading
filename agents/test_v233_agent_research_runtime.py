import copy
import unittest
from datetime import datetime, timezone, timedelta
from agent_research_runtime_v233 import build_research, SYMBOLS

NOW = datetime(2026, 10, 31, 6, tzinfo=timezone.utc)

def source():
    return {
        "version": "V229.0", "report_type": "DETERMINISTIC_COMMANDER_RESEARCH_BRIEF",
        "research_only": True, "orders_enabled": False, "realtime": False,
        "ai_agents_running": False, "trade_signals_available": False,
        "backtest_verified": False, "commander": {"status": "COMPILED_NOT_AI"},
        "source_generated_at_utc": (NOW - timedelta(minutes=10)).isoformat(),
        "generated_at_utc": (NOW - timedelta(minutes=5)).isoformat(),
        "markets": [{"symbol": s, "trend_observation": "SMA50_ABOVE_SMA200",
                     "volume_ratio_20": 1.2, "risk_status": "NO_TRADE_AUTHORIZATION",
                     "research_conclusion": "DESCRIPTIVE_ONLY"} for s in SYMBOLS]
    }

class RuntimeTests(unittest.TestCase):
    def test_produces_explicit_non_ai_contract(self):
        result = build_research(source(), NOW)
        self.assertEqual(len(result["markets"]), 3)
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["ai_agents_running"])
        self.assertFalse(result["model_inference_performed"])
        self.assertIsNone(result["markets"][0]["COMMANDER"]["recommendation"])

    def test_rejects_unsafe_flags(self):
        for key in ("orders_enabled", "ai_agents_running", "trade_signals_available", "backtest_verified"):
            payload = source()
            payload[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_research(payload, NOW)

    def test_rejects_bad_provenance(self):
        for field, time in (("source_generated_at_utc", NOW - timedelta(hours=9)),
                            ("source_generated_at_utc", NOW + timedelta(minutes=1)),
                            ("generated_at_utc", NOW + timedelta(minutes=1))):
            payload = source()
            payload[field] = time.isoformat()
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_research(payload, NOW)

    def test_rejects_duplicate_and_unsafe_markets(self):
        payload = source()
        payload["markets"][1]["symbol"] = SYMBOLS[0]
        with self.assertRaises(ValueError):
            build_research(payload, NOW)
        payload = source()
        payload["markets"][0]["risk_status"] = "TRADE_ALLOWED"
        with self.assertRaises(ValueError):
            build_research(payload, NOW)

    def test_rejects_nonfinite_and_boolean_ratio(self):
        for value in (float("nan"), float("inf"), True, -1):
            payload = source()
            payload["markets"][0]["volume_ratio_20"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_research(payload, NOW)

if __name__ == "__main__":
    unittest.main()
