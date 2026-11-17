"""Exercise real local CLIs; live inference is deliberately never enabled."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_v233_agent_research_runtime import source

AGENTS = Path(__file__).resolve().parent


class CliChainTests(unittest.TestCase):
    def run_cli(self, name, *arguments, cwd):
        environment = dict(os.environ, OPENAI_API_KEY='fixture-key-never-send')
        result = subprocess.run([sys.executable, str(AGENTS/name), *map(str, arguments)],
                                cwd=cwd, env=environment, text=True,
                                capture_output=True, timeout=15)
        self.assertNotIn('fixture-key-never-send', result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return result

    def test_prepare_setup_and_disabled_runtime_from_external_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            brief = Path(directory)/'market brief.json'
            bundle = Path(directory)/'prepared bundle.json'
            transcript = Path(directory)/'completed meeting.json'
            payload = source()
            now = datetime.now(timezone.utc)
            payload['source_generated_at_utc'] = (now-timedelta(minutes=10)).isoformat()
            payload['generated_at_utc'] = (now-timedelta(minutes=5)).isoformat()
            brief.write_text(json.dumps(payload), encoding='utf-8')
            original = brief.read_bytes()
            prepared = self.run_cli('ai_meeting_prepare.py', brief, bundle, cwd=directory)
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            self.assertEqual(json.loads(prepared.stdout)['status'], 'BUNDLE_PREPARED')
            before_check = bundle.read_bytes()
            checked = self.run_cli('ai_meeting_setup.py', bundle, '--model', 'test-model', cwd=directory)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            setup = json.loads(checked.stdout.splitlines()[0])
            self.assertEqual(setup['status'], 'LOCAL_SETUP_VALID')
            self.assertFalse(setup['provider_verified'])
            self.assertEqual(setup['model_calls_performed'], 0)
            # Running the real runtime without the paid opt-in must still stop.
            runtime = self.run_cli('ai_meeting_runtime.py', bundle, transcript,
                                   '--model', 'test-model', cwd=directory)
            self.assertEqual(runtime.returncode, 1)
            self.assertIn('LIVE_PROVIDER_NOT_ENABLED', runtime.stderr)
            self.assertFalse(transcript.exists())
            self.assertEqual(brief.read_bytes(), original)
            self.assertEqual(bundle.read_bytes(), before_check)
            self.assertEqual(set(Path(directory).iterdir()), {brief, bundle})

    def test_cli_errors_return_nonzero_without_corrupting_output(self):
        with tempfile.TemporaryDirectory() as directory:
            brief, target = Path(directory)/'brief.json', Path(directory)/'bundle.json'
            target.write_bytes(b'previous bundle')
            brief.write_text('private malformed input', encoding='utf-8')
            result = self.run_cli('ai_meeting_prepare.py', brief, target, cwd=directory)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['error_code'], 'INVALID_JSON')
            self.assertNotIn('private malformed input', result.stdout + result.stderr)
            self.assertEqual(target.read_bytes(), b'previous bundle')
            result = self.run_cli('ai_meeting_prepare.py', brief, brief, cwd=directory)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['error_code'], 'PATH_ALIAS')
            self.assertEqual(brief.read_text(), 'private malformed input')


if __name__ == '__main__':
    unittest.main()
