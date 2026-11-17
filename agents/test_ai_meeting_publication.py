from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from ai_meeting_runtime import run_meeting, MeetingError
from ai_meeting_publication import validate_public_report, restore_previous, PUBLIC_URL, MAX_BYTES
from test_ai_meeting_runtime import Fixture
from test_v240_provider_transport_preflight import request, NOW


def live_fixture():
    # Synthetic unit-test snapshot only. Never produced as a CI artifact or published.
    value = run_meeting(request(), Fixture(), clock=lambda: NOW)
    value.update(execution_mode='LIVE_PROVIDER', model_inference_performed=True, model='test-model')
    return value


class PublicationTests(unittest.TestCase):
    def test_optional_workflow_execution_identity_is_strict(self):
        value = live_fixture()
        value['workflow_execution_id'] = 'a'*32
        validated = validate_public_report(value, now=NOW)
        self.assertEqual(validated['workflow_execution_id'], 'a'*32)
        for invalid in [None, '', 'A'*32, 'a'*31, ['a'*32]]:
            value['workflow_execution_id'] = invalid
            with self.assertRaises(MeetingError):
                validate_public_report(value, now=NOW)

    def test_actual_manual_workflow_guard_blocks_unconfigured_or_unapproved_calls(self):
        root = Path(__file__).resolve().parent.parent
        workflow = (root/'.github/workflows/run_ai_meeting.yml').read_text()
        triggers = workflow.split('on:\n', 1)[1].split('permissions:', 1)[0]
        self.assertIn('workflow_dispatch:', triggers)
        self.assertNotIn('schedule:', triggers)
        self.assertNotIn('push:', triggers)
        self.assertIn('default: false', triggers)
        code = textwrap.dedent(workflow.split("python - <<'PY'\n", 1)[1].split('\n          PY\n', 1)[0])
        configured = {'OPENAI_API_KEY': 'test-secret-never-logged', 'SPACEBAR_AI_MODEL': 'test-model',
                      'SPACEBAR_REF': 'refs/heads/main', 'SPACEBAR_AI_AUTHORIZED': 'true'}
        cases = [({}, True), ({'SPACEBAR_AI_AUTHORIZED': 'false'}, False),
                 ({'SPACEBAR_REF': 'refs/heads/feature'}, False),
                 ({'SPACEBAR_AI_MODEL': ''}, False), ({'OPENAI_API_KEY': ''}, False)]
        for overrides, allowed in cases:
            result = subprocess.run([sys.executable, '-c', code],
                                    env={**os.environ, **configured, **overrides},
                                    text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode == 0, allowed, result.stderr)
            self.assertNotIn(configured['OPENAI_API_KEY'], result.stdout+result.stderr)
        default_workflow = (root/'.github/workflows/deploy_browser_room.yml').read_text()
        self.assertNotIn('secrets.', default_workflow)
        self.assertNotIn('--enable-live', default_workflow)
        self.assertIn('--model "$SPACEBAR_AI_MODEL"', workflow)

    def test_exact_bundle_validation_and_input_not_mutated(self):
        report = live_fixture()
        result = validate_public_report(report, bundle=request(), now=NOW)
        result['transcript'][0]['summary'] = 'changed'
        self.assertNotEqual(report['transcript'][0]['summary'], 'changed')

    def test_offline_fixture_cannot_be_published(self):
        fixture = run_meeting(request(), Fixture(), clock=lambda: NOW)
        with self.assertRaises(MeetingError):
            validate_public_report(fixture, now=NOW)

    def test_wrong_bundle_and_source_hash_are_rejected(self):
        for mode in ('hash', 'source'):
            report = live_fixture()
            if mode == 'hash':
                report['request_sha256'] = '0'*64
            else:
                report['source_generated_at_utc'] = (NOW-timedelta(minutes=20)).isoformat()
            with self.subTest(mode=mode), self.assertRaises(MeetingError):
                validate_public_report(report, bundle=request(), now=NOW)

    def test_unsafe_incomplete_and_unexpected_fields_are_rejected(self):
        mutations = [lambda r: r.update(orders_enabled=True),
                     lambda r: r.update(ai_agents_running=True),
                     lambda r: r.update(model_inference_performed=1),
                     lambda r: r.update(api_key='not-allowed'),
                     lambda r: r.update(call_count=True),
                     lambda r: r.update(final_verdict='BUY'),
                     lambda r: r['transcript'].pop(),
                     lambda r: r['transcript'][0].update(phase='CONCLUSION'),
                     lambda r: r['transcript'][0].update(agent='COMMANDER'),
                     lambda r: r['transcript'][0].update(unknown='not-allowed'),
                     lambda r: r['transcript'][0].update(summary=''),
                     lambda r: r.update(request_sha256='bad')]
        for mutate in mutations:
            report = live_fixture()
            mutate(report)
            with self.subTest(report=report), self.assertRaises(ValueError):
                validate_public_report(report, now=NOW)

    def test_veto_must_match_effective_conclusion(self):
        for objection in ('REVIEW_NEEDED', 'INSUFFICIENT_DATA'):
            report = live_fixture()
            report['transcript'][2]['verdict'] = objection
            with self.assertRaises(MeetingError):
                validate_public_report(report, now=NOW)
            report['final_verdict'] = objection
            self.assertEqual(validate_public_report(report, now=NOW)['final_verdict'], objection)

    def test_expiry_boundary_and_future_times(self):
        report = live_fixture()
        source = NOW-timedelta(minutes=10)
        validate_public_report(report, now=source+timedelta(hours=8))
        for when in (source+timedelta(hours=8, microseconds=1), NOW-timedelta(seconds=1)):
            with self.subTest(now=when), self.assertRaises(MeetingError):
                validate_public_report(report, now=when)
        report['started_at_utc'] = (source-timedelta(seconds=1)).isoformat()
        with self.assertRaises(MeetingError):
            validate_public_report(report, now=NOW)

    def test_restore_uses_fixed_url_bounded_read_and_no_provider(self):
        with tempfile.TemporaryDirectory() as directory, patch('ai_meeting_publication.build_opener') as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.read.return_value = json.dumps(live_fixture()).encode()
            target = Path(directory)/'meeting.json'
            with patch('ai_meeting_runtime.OpenAIProvider.complete', side_effect=AssertionError('no model call')):
                self.assertTrue(restore_previous(target, now=NOW))
            self.assertEqual(json.loads(target.read_text())['execution_mode'], 'LIVE_PROVIDER')
            opener.return_value.open.assert_called_once_with(PUBLIC_URL, timeout=10)
            response.read.assert_called_once_with(MAX_BYTES+1)

    def test_missing_stale_fixture_malformed_and_oversize_clear_candidate(self):
        values = [b'not-json', b'x'*(MAX_BYTES+1),
                  json.dumps(run_meeting(request(), Fixture(), clock=lambda: NOW)).encode(),
                  json.dumps(live_fixture()).encode()]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'meeting.json'
            for raw in values:
                target.write_text('old candidate')
                with patch('ai_meeting_publication.build_opener') as opener:
                    opener.return_value.open.return_value.__enter__.return_value.read.return_value = raw
                    self.assertFalse(restore_previous(target, now=NOW+timedelta(hours=9)))
                self.assertFalse(target.exists())
            target.write_text('old candidate')
            with patch('ai_meeting_publication.build_opener') as opener:
                opener.return_value.open.side_effect = HTTPError(PUBLIC_URL, 404, '', {}, None)
                self.assertFalse(restore_previous(target, now=NOW))
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
