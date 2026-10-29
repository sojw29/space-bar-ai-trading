"""V201 local static scorecard API contract and fail-closed validation."""
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from test_v28_api import LocalApiTests


class ScorecardAPIContractTests(LocalApiTests):
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
