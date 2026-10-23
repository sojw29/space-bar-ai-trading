"""V29 HTML and local HTTP smoke tests."""
import sys
import unittest
from pathlib import Path
from urllib.request import urlopen
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v28_api import LocalApiTests


class DashboardTests(LocalApiTests):
    def test_dashboard_html_served_same_origin(self):
        with urlopen(self.base + "/dashboard", timeout=3) as response:
            html = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.headers["Content-Type"])
            self.assertIn("SPACE BAR", html)
            self.assertIn('fetch("/api/v1/agents"', html)
            self.assertIn("PAPER RESEARCH ONLY", html)

    def test_root_dashboard(self):
        with urlopen(self.base + "/", timeout=3) as response:
            self.assertEqual(response.status, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
