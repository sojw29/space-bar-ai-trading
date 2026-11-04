"""Check dashboard inline JavaScript parses without starting a browser/server."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ROOT / "web" / "command_center.html",
    ROOT / "web" / "audit_room_mobile_v153.html",
]


class TestDashboardJavaScriptSyntax(unittest.TestCase):
    def test_inline_scripts_parse_with_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js not installed (required in CI)")
        for page in PAGES:
            with self.subTest(page=page.name):
                html = page.read_text(encoding="utf-8")
                scripts = re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script\\s*>", html, re.S | re.I)
                self.assertTrue(scripts, "missing inline script")
                for script in scripts:
                    with tempfile.TemporaryDirectory() as directory:
                        js = Path(directory) / "inline.js"
                        js.write_text(script, encoding="utf-8")
                        result = subprocess.run(
                            [node, "--check", str(js)],
                            capture_output=True, text=True, timeout=10, check=False,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
