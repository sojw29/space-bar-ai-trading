"""V205 snapshot freshness classifier: boundary and fail-closed tests."""
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scorecard_freshness_v205 import assess


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def report(hours):
    return {"version":"V105.0","research_only":True,"orders_enabled":False,
            "live_trading_approved":False,
            "snapshot_provenance":{"version":"V204.0","research_only":True,
                "realtime":False,"data_authenticity_verified":False,
                "history_timestamp_verified":False,
                "generated_at_utc":(NOW-timedelta(hours=hours)).isoformat().replace("+00:00","Z")}}


class FreshnessTests(unittest.TestCase):
    def test_boundaries(self):
        for age,expected in [(0,"RECENT_SNAPSHOT"),(24,"RECENT_SNAPSHOT"),
                             (25,"AGING_SNAPSHOT"),(72,"AGING_SNAPSHOT"),
                             (73,"STALE_SNAPSHOT")]:
            with self.subTest(age=age):
                result=assess(report(age),now=NOW)
                self.assertEqual(result["status"],expected)
                self.assertFalse(result["orders_allowed"])
                self.assertFalse(result["market_data_freshness_verified"])

    def test_future_and_missing(self):
        self.assertEqual(assess(report(-1),now=NOW)["status"],"UNKNOWN")
        data=report(1)
        del data["snapshot_provenance"]
        self.assertEqual(assess(data,now=NOW)["status"],"UNKNOWN")

    def test_non_utc_and_implausibly_old_timestamps_fail_closed(self):
        data=report(1)
        data["snapshot_provenance"]["generated_at_utc"]="2026-10-29T12:00:00+00:00"
        self.assertEqual(assess(data,now=NOW)["status"],"UNKNOWN")
        self.assertEqual(assess(report(24*3651),now=NOW)["status"],"UNKNOWN")

    def test_unsafe_report_rejected(self):
        data=report(1)
        data["orders_enabled"]=True
        with self.assertRaises(ValueError):
            assess(data,now=NOW)

    def test_room_has_generation_age_warnings(self):
        html=(Path(__file__).resolve().parents[1]/"web"/"office_3d.html").read_text(encoding="utf-8")
        self.assertIn("오래된 스냅샷(72시간 초과)",html)
        self.assertIn("최근 생성된 스냅샷",html)
        self.assertIn("생성 시각 오류",html)
        self.assertIn('!p.generated_at_utc.endsWith("Z")',html)
        self.assertIn("생성 시각 범위 오류",html)


if __name__=="__main__":
    unittest.main()
