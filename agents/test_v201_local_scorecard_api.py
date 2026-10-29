"""V201 local static scorecard API contract and fail-closed validation."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

import dashboard_api_v28 as v28
from test_v28_api import LocalApiTests
from test_v199_strategy_scorecard_html import sample


class ScorecardAPIContractTests(LocalApiTests):
    def request_with_snapshot(self, raw_bytes):
        # Isolate test input from the repository's actual reports directory.
        with tempfile.TemporaryDirectory() as root:
            fake_module = Path(root) / "agents" / "dashboard_api_v28.py"
            fake_module.parent.mkdir()
            scorecard = Path(root) / "reports" / "strategy_scorecard_latest.json"
            scorecard.parent.mkdir()
            scorecard.write_bytes(raw_bytes)
            with patch.object(v28, "__file__", str(fake_module)):
                return self.get("/api/v1/research/scorecard")

    def test_valid_snapshot_is_read_only(self):
        status, payload = self.request_with_snapshot(json.dumps(sample()).encode("utf-8"))
        self.assertEqual(status, 200)
        self.assertFalse(payload["orders_enabled"])
        self.assertFalse(payload["strategy_scorecard"]["orders_allowed"])

    def test_invalid_utf8_snapshot_returns_503(self):
        with self.assertRaises(HTTPError) as caught:
            self.request_with_snapshot(bytes([0xff]))
        self.assertEqual(caught.exception.code, 503)
        self.assertIn(b"offline_scorecard_invalid", caught.exception.read())

    def test_unsafe_snapshot_returns_503(self):
        report = sample()
        report["orders_enabled"] = True
        with self.assertRaises(HTTPError) as caught:
            self.request_with_snapshot(json.dumps(report).encode("utf-8"))
        self.assertEqual(caught.exception.code, 503)

    def test_response_over_shared_limit_returns_503(self):
        report = sample()
        report["padding"] = "x" * 1_000_000
        with self.assertRaises(HTTPError) as caught:
            self.request_with_snapshot(json.dumps(report).encode("utf-8"))
        self.assertEqual(caught.exception.code, 503)

    def test_invalid_snapshot_is_not_exposed(self):
        # Force the endpoint to reject the snapshot even if a file exists.
        original_is_file = Path.is_file
        def missing_scorecard(path):
            if path.name == "strategy_scorecard_latest.json":
                return False
            return original_is_file(path)
        with patch.object(Path, "is_file", missing_scorecard):
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.base + "/api/v1/research/scorecard", timeout=3)
            self.assertEqual(caught.exception.code, 404)
            self.assertIn(b"offline_scorecard_not_available", caught.exception.read())

    def test_endpoint_does_not_allow_post(self):
        from urllib.request import Request
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.base + "/api/v1/research/scorecard",
                            data=b"{}", method="POST"), timeout=3)
        self.assertNotEqual(caught.exception.code, 200)


if __name__ == "__main__":
    unittest.main()
