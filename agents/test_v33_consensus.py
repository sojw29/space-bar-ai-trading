"""V33 consensus-flow static safety and UI contracts."""
import unittest
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "web" / "command_center.html"


class ConsensusFlowTests(unittest.TestCase):
    def test_vote_flow_ui(self):
        content = HTML.read_text(encoding="utf-8")
        for key in ('id="consensus-panel"', 'id="consensus-votes"',
                    'id="consensus-tally"', 'id="consensus-conflict"',
                    'id="consensus-veto"', 'function renderConsensus(envelope)',
                    'commander.long_votes!==longs', 'commander.short_votes!==shorts',
                    'commander.decision!==expected'):
            self.assertIn(key, content)

    def test_disconnection_clears_flow(self):
        content = HTML.read_text(encoding="utf-8")
        self.assertIn('function resetConsensus()', content)
        self.assertIn('resetConsensus();', content)
        self.assertIn('lastFailure=true;', content)

    def test_no_fake_communication_or_trade_execution(self):
        content = HTML.read_text(encoding="utf-8")
        self.assertIn('실제 AI 간 대화가 아니라', content)
        self.assertIn('PAPER RESEARCH ONLY', content)
        self.assertNotIn('innerHTML=', content)
        self.assertNotIn('fetch("/api/v1/orders"', content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
