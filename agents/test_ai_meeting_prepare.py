"""Actual preparation chain, atomic publication and failure preservation."""
from datetime import timedelta
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_meeting_prepare import prepare_file
from ai_meeting_runtime import run_meeting
from provider_transport_preflight_v240 import preflight
from test_ai_meeting_runtime import Fixture
from test_v233_agent_research_runtime import source, NOW


class PreparationTests(unittest.TestCase):
    def test_prepared_bundle_is_accepted_by_real_runtime_without_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            brief, target = Path(directory)/'brief.json', Path(directory)/'bundle.json'
            brief.write_text(json.dumps(source()), encoding='utf-8')
            before = brief.read_bytes()
            with patch('socket.socket', side_effect=AssertionError('network')), patch(
                    'ai_meeting_runtime.OpenAIProvider.__init__', side_effect=AssertionError('provider')):
                result = prepare_file(brief, target, now=NOW)
            self.assertEqual(result['status'], 'BUNDLE_PREPARED')
            self.assertEqual(result['model_calls_performed'], 0)
            self.assertEqual(brief.read_bytes(), before)
            bundle = json.loads(target.read_text(encoding='utf-8'))
            preflight(bundle, dry_run=True, now=NOW)
            report = run_meeting(bundle, Fixture(), clock=lambda: NOW)
            self.assertEqual(report['status'], 'COMPLETED')
            self.assertEqual(report['call_count'], 7)
            self.assertFalse(report['model_inference_performed'])
            self.assertFalse(report['orders_enabled'])

    def test_invalid_inputs_preserve_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            brief, target = Path(directory)/'brief.json', Path(directory)/'bundle.json'
            target.write_bytes(b'previous')
            for data in [b'private-invalid-input', b'null', b'x'*65537]:
                brief.write_bytes(data)
                result = prepare_file(brief, target, now=NOW)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertEqual(target.read_bytes(), b'previous')
                self.assertNotIn('private-invalid-input', json.dumps(result))
            brief.write_text(json.dumps(source()), encoding='utf-8')
            self.assertEqual(prepare_file(brief, target, now=NOW+timedelta(hours=9))['status'], 'BLOCKED')
            self.assertEqual(target.read_bytes(), b'previous')

    def test_aliases_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as directory:
            brief = Path(directory)/'brief.json'
            brief.write_text(json.dumps(source()), encoding='utf-8')
            original = brief.read_bytes()
            hard, link = Path(directory)/'hard.json', Path(directory)/'link.json'
            os.link(brief, hard)
            link.symlink_to(brief)
            for target in [brief, hard, link]:
                self.assertEqual(prepare_file(brief, target, now=NOW)['status'], 'BLOCKED')
                self.assertEqual(brief.read_bytes(), original)

    def test_expiry_and_backward_clock_before_publication_preserve_output(self):
        with tempfile.TemporaryDirectory() as directory:
            brief, target = Path(directory)/'brief.json', Path(directory)/'bundle.json'
            brief.write_text(json.dumps(source()), encoding='utf-8')
            target.write_bytes(b'previous')
            for last in [NOW+timedelta(hours=9), NOW-timedelta(seconds=1)]:
                times = iter([NOW]*5+[last])
                result = prepare_file(brief, target, clock=lambda: next(times))
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertEqual(result['stage'], 'PUBLICATION')
                self.assertEqual(target.read_bytes(), b'previous')


if __name__ == '__main__':
    unittest.main()
