"""Behavioral regression checks for the read-only V231 local comparison panel."""
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOM = (Path(__file__).resolve().parent.parent / "web" / "office_3d.html").read_text(encoding="utf-8")
SCRIPT = re.search(
    r"/\\* V231: compare two verified local research snapshots, not trading signals\\. \\*/\\s*(.*?)</script>",
    ROOM,
    re.S,
)
NODE_RUNNER = r"""
const vm = require('vm');
const script = process.argv[1];
const records = JSON.parse(process.argv[2]);
const elements = {};
const document = {
  getElementById(id) {
    if (!elements[id]) elements[id] = {
      textContent: '', children: [],
      replaceChildren(...children) { this.children = children; },
      addEventListener(_event, fn) { this.handler = fn; }
    };
    return elements[id];
  },
  createElement(_tag) { return { textContent: '' }; }
};
const localStorage = { getItem(_key) { return JSON.stringify(records); } };
vm.runInNewContext(script, { document, localStorage, Date });
console.log(JSON.stringify({
  status: elements['v231-status'].textContent,
  rows: elements['v231-rows'].children.map(row => row.textContent)
}));
"""


def snapshot(timestamp, ratio=1.0):
    return {
        "timestamp": timestamp,
        "markets": [
            {"symbol": symbol, "trend": "SMA50_ABOVE_SMA200", "ratio": ratio}
            for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT")
        ],
    }


class LocalComparisonTests(unittest.TestCase):
    def run_comparison(self, records):
        self.assertIsNotNone(SCRIPT, "V231 comparison script must exist")
        proc = subprocess.run(
            ["node", "-e", NODE_RUNNER, SCRIPT.group(1), json.dumps(records)],
            check=True, capture_output=True, text=True, timeout=10,
        )
        return json.loads(proc.stdout)

    def test_two_valid_snapshots_render_descriptive_comparison(self):
        result = self.run_comparison([
            snapshot("2026-10-25T00:00:00Z", 1.0),
            snapshot("2026-10-26T00:00:00Z", 1.25),
        ])
        self.assertEqual(len(result["rows"]), 3)
        self.assertIn("+0.2500", result["rows"][0])
        self.assertNotIn("비교 불가", result["status"])

    def test_invalid_record_must_not_be_silently_discarded(self):
        result = self.run_comparison([
            snapshot("2026-10-25T00:00:00Z"),
            {"timestamp": "2026-10-25T12:00:00Z", "markets": []},
            snapshot("2026-10-26T00:00:00Z"),
        ])
        self.assertEqual(result["rows"], [])
        self.assertIn("비교 불가", result["status"])

    def test_conflicting_duplicate_timestamp_fails_closed(self):
        result = self.run_comparison([
            snapshot("2026-10-25T00:00:00Z"),
            snapshot("2026-10-26T00:00:00Z", 1.1),
            snapshot("2026-10-26T00:00:00Z", 1.9),
        ])
        self.assertEqual(result["rows"], [])
        self.assertIn("중복 기록 시각", result["status"])

    def test_one_snapshot_cannot_produce_comparison(self):
        result = self.run_comparison([snapshot("2026-10-26T00:00:00Z")])
        self.assertEqual(result["rows"], [])
        self.assertIn("2개 필요", result["status"])


if __name__ == "__main__":
    unittest.main()
