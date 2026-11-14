"""Default workflow cannot execute a model; opt-in routing tested with fixtures only."""
from datetime import datetime, timedelta, timezone
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_meeting_workflow import run_workflow
from test_ai_meeting_runtime import Fixture
from test_v233_agent_research_runtime import source


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.brief = Path(self.temp.name)/'brief.json'
        self.target = Path(self.temp.name)/'transcript.json'
        payload = source()
        now = datetime.now(timezone.utc)
        payload['source_generated_at_utc'] = (now-timedelta(minutes=10)).isoformat()
        payload['generated_at_utc'] = (now-timedelta(minutes=5)).isoformat()
        self.brief.write_text(json.dumps(payload), encoding='utf-8')
        self.target.write_bytes(b'previous report')
        self.key = patch.dict(os.environ, {'OPENAI_API_KEY': 'private-fixture-key'})
        self.key.start()
        self.addCleanup(self.key.stop)

    def test_default_checks_only_and_preserves_destination(self):
        with patch('ai_meeting_workflow.run_meeting', side_effect=AssertionError('inference')) as run:
            result = run_workflow(self.brief, self.target, 'test-model')
        self.assertEqual(result['status'], 'READY_NO_MODEL_CALLS')
        self.assertEqual(result['model_calls_performed'], 0)
        self.assertFalse(result['provider_verified'])
        run.assert_not_called()
        self.assertEqual(self.target.read_bytes(), b'previous report')
        self.assertNotIn('private-fixture-key', json.dumps(result))

    def test_explicit_opt_in_uses_real_runtime_with_offline_fixture_only(self):
        with patch('ai_meeting_workflow.OpenAIProvider', return_value=Fixture()) as provider:
            result = run_workflow(self.brief, self.target, 'test-model', enable_live=True)
        provider.assert_called_once_with(enabled=True, model='test-model')
        self.assertEqual(result['status'], 'COMPLETED')
        self.assertEqual(result['model_calls_performed'], 0)
        self.assertEqual(result['validated_responses'], 7)
        report = json.loads(self.target.read_text())
        self.assertEqual(report['call_count'], 7)
        self.assertFalse(report['model_inference_performed'])
        self.assertFalse(report['orders_enabled'])

    def test_input_and_setup_failures_never_execute(self):
        with patch('ai_meeting_workflow.run_meeting', side_effect=AssertionError('inference')):
            with patch.dict(os.environ, {}, clear=True):
                result = run_workflow(self.brief, self.target, 'test-model', enable_live=True)
            self.assertEqual(result['workflow_stage'], 'SETUP')
            self.assertEqual(result['error_code'], 'OPENAI_API_KEY_REQUIRED')
            self.brief.write_text('private invalid input')
            result = run_workflow(self.brief, self.target, 'test-model', enable_live=True)
            self.assertEqual(result['workflow_stage'], 'PREPARATION')
            self.assertNotIn('private invalid input', json.dumps(result))
        self.assertEqual(self.target.read_bytes(), b'previous report')

    def test_alias_and_inference_failure_preserve_files(self):
        before = self.brief.read_bytes()
        result = run_workflow(self.brief, self.brief, 'test-model', enable_live=True)
        self.assertEqual(result['error_code'], 'SOURCE_DESTINATION_ALIAS')
        self.assertEqual(self.brief.read_bytes(), before)
        with patch('ai_meeting_workflow.run_meeting', side_effect=ValueError('private failure')):
            result = run_workflow(self.brief, self.target, 'test-model', enable_live=True)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertIsNone(result['model_calls_performed'])
        self.assertNotIn('private failure', json.dumps(result))
        self.assertEqual(self.target.read_bytes(), b'previous report')

    def cli(self, *, key='private-fixture-key'):
        command = [sys.executable, str(Path(__file__).resolve().with_name('ai_meeting_workflow.py')),
                   str(self.brief), str(self.target), '--model', 'test-model', '--json']
        result = subprocess.run(command, cwd=self.temp.name,
                                env=dict(os.environ, OPENAI_API_KEY=key),
                                capture_output=True, text=True, timeout=15)
        self.assertNotIn('private-fixture-key', result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        return result, json.loads(result.stdout)

    def test_cli_json_default_has_one_result_and_preserves_existing_output(self):
        self.brief = self.brief.rename(self.brief.with_name('market brief with spaces.json'))
        self.target = self.target.rename(self.target.with_name('previous transcript with spaces.json'))
        result, payload = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload['status'], 'READY_NO_MODEL_CALLS')
        self.assertEqual(payload['model_calls_performed'], 0)
        self.assertFalse(payload['provider_verified'])
        self.assertIn('Local checks only', result.stderr)
        self.assertEqual(self.target.read_bytes(), b'previous report')

    def test_cli_json_missing_key_fails_without_replacing_transcript(self):
        result, payload = self.cli(key='')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload['workflow_stage'], 'SETUP')
        self.assertEqual(payload['error_code'], 'OPENAI_API_KEY_REQUIRED')
        self.assertEqual(payload['model_calls_performed'], 0)
        self.assertEqual(self.target.read_bytes(), b'previous report')

    def test_cli_json_invalid_input_has_sanitized_preparation_failure(self):
        self.brief.write_text('private invalid source')
        result, payload = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload['workflow_stage'], 'PREPARATION')
        self.assertEqual(payload['error_code'], 'INVALID_JSON')
        self.assertNotIn('private invalid source', result.stdout + result.stderr)
        self.assertEqual(self.target.read_bytes(), b'previous report')


if __name__ == '__main__':
    unittest.main()
