from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone, timedelta
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from ai_meeting_runtime import OpenAIProvider, MeetingError, main, run_meeting
from ai_meeting_diagnostics import read_summary, render_status
from test_ai_meeting_runtime import Fixture, statement
from test_v240_provider_transport_preflight import request, NOW


def current_bundle():
    value = request()
    now = datetime.now(timezone.utc)
    value['source_generated_at_utc'] = (now-timedelta(minutes=2)).isoformat()
    value['generated_at_utc'] = (now-timedelta(minutes=1)).isoformat()
    return value


class DiagnosticTests(unittest.TestCase):
    def test_progress_counts_validated_responses_separately_from_attempts(self):
        events = []
        run_meeting(request(), Fixture(), clock=lambda: NOW, progress=events.append)
        self.assertEqual(len(events), 14)
        self.assertEqual(events[0]['attempted_calls'], 1)
        self.assertEqual(events[0]['validated_responses'], 0)
        self.assertEqual(events[-1], {'agent': 'COMMANDER', 'phase': 'CONCLUSION',
                                     'event': 'RESPONSE_VALIDATED', 'attempted_calls': 7,
                                     'validated_responses': 7})

    def test_http_classes_redact_raw_details_without_retry(self):
        expected = {400: 'PROVIDER_REQUEST_REJECTED', 401: 'PROVIDER_AUTHENTICATION_FAILED',
                    403: 'PROVIDER_ACCESS_DENIED', 404: 'PROVIDER_MODEL_OR_ENDPOINT_NOT_FOUND',
                    429: 'PROVIDER_RATE_OR_QUOTA_LIMIT', 500: 'PROVIDER_UPSTREAM_ERROR',
                    503: 'PROVIDER_UPSTREAM_ERROR', 418: 'PROVIDER_REQUEST_FAILED'}
        for status, code in expected.items():
            with self.subTest(status=status), patch('ai_meeting_runtime.build_opener') as opener:
                opener.return_value.open.side_effect = HTTPError('secret-url', status, 'secret-key', {}, None)
                provider = OpenAIProvider(enabled=True, model='test', api_key='secret-key')
                with self.assertRaisesRegex(MeetingError, '^'+code+'$'):
                    provider.complete('ATLAS', 'ANALYSIS', {})
                self.assertEqual(opener.return_value.open.call_count, 1)

    def test_timeout_and_incomplete_output_are_distinct(self):
        cases = [(TimeoutError('secret'), 'PROVIDER_TIMEOUT'),
                 (URLError(TimeoutError('secret')), 'PROVIDER_TIMEOUT'),
                 (URLError('secret'), 'PROVIDER_REQUEST_FAILED')]
        for error, code in cases:
            with patch('ai_meeting_runtime.build_opener') as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaisesRegex(MeetingError, '^'+code+'$'):
                    OpenAIProvider(enabled=True, model='test', api_key='secret').complete('ATLAS', 'ANALYSIS', {})
        for finish, refusal, code in [('length', None, 'PROVIDER_OUTPUT_TRUNCATED'),
                                      ('stop', 'secret refusal', 'PROVIDER_REFUSED')]:
            with patch('ai_meeting_runtime.build_opener') as opener:
                raw = {'choices': [{'finish_reason': finish, 'message': {'content': '{}', 'refusal': refusal}}]}
                opener.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps(raw).encode()
                with self.assertRaisesRegex(MeetingError, '^'+code+'$'):
                    OpenAIProvider(enabled=True, model='test', api_key='secret').complete('ATLAS', 'ANALYSIS', {})

    def invoke(self, source, output, status, *, responses=None, key='secret-key'):
        out, err = io.StringIO(), io.StringIO()
        argv = ['ai_meeting_runtime.py', str(source), str(output), '--enable-live', '--model', 'test', '--diagnostics', str(status)]
        with patch.object(sys, 'argv', argv), patch.dict(os.environ, {'OPENAI_API_KEY': key}), \
                patch.object(OpenAIProvider, 'complete', side_effect=responses or [statement()]*7) as complete, \
                redirect_stdout(out), redirect_stderr(err):
            code = 0
            try:
                main()
            except SystemExit as exit:
                code = exit.code
        return code, out.getvalue()+err.getvalue(), complete.call_count

    def test_partial_failure_records_phase_and_preserves_previous_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target, status = [Path(directory)/n for n in ('source.json', 'meeting.json', 'status.json')]
            source.write_text(json.dumps(current_bundle()))
            target.write_text('previous completed snapshot')
            code, text, calls = self.invoke(source, target, status, responses=[statement(), MeetingError('PROVIDER_RATE_OR_QUOTA_LIMIT')])
            self.assertEqual(code, 1)
            self.assertEqual(calls, 2)
            self.assertEqual(target.read_text(), 'previous completed snapshot')
            self.assertNotIn('secret-key', text+status.read_text())
            record = json.loads(status.read_text())
            self.assertEqual((record['agent'], record['phase']), ('QUANT', 'ANALYSIS'))
            self.assertEqual((record['attempted_calls'], record['validated_responses']), (2, 1))
            self.assertEqual(record['error_code'], 'PROVIDER_RATE_OR_QUOTA_LIMIT')
            summary = render_status(record)
            self.assertIn('2/7', summary)
            self.assertIn('결제 금액이나 실제 과금 횟수가 아닙니다', summary)

    def test_completed_run_summary_does_not_claim_pages_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target, status = [Path(directory)/n for n in ('source.json', 'meeting.json', 'status.json')]
            source.write_text(json.dumps(current_bundle()))
            code, text, calls = self.invoke(source, target, status)
            self.assertEqual((code, calls), (0, 7))
            self.assertEqual(json.loads(status.read_text())['status'], 'COMPLETED')
            self.assertEqual(len(json.loads(target.read_text())['transcript']), 7)
            self.assertIn('Pages 배포 성공은 이후 단계에서 별도로 확인', read_summary(status))
            self.assertNotIn('secret-key', text+status.read_text())

    def test_interruption_preserves_running_status_before_provider_returns(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target, status = [Path(directory)/n for n in ('source.json', 'meeting.json', 'status.json')]
            source.write_text(json.dumps(current_bundle()))
            target.write_text('previous completed snapshot')
            def interrupt(*args):
                record = json.loads(status.read_text())
                self.assertEqual(record['status'], 'RUNNING')
                self.assertEqual((record['attempted_calls'], record['validated_responses']), (1, 0))
                raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):
                self.invoke(source, target, status, responses=interrupt)
            self.assertEqual(target.read_text(), 'previous completed snapshot')
            summary = read_summary(status)
            self.assertIn('RUNNING', summary)
            self.assertIn('회의 완료나 공개 게시 성공을 의미하지 않습니다', summary)

    def test_missing_key_has_no_attempts_and_input_alias_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target, status = [Path(directory)/n for n in ('source.json', 'meeting.json', 'status.json')]
            source.write_text(json.dumps(current_bundle()))
            original = source.read_text()
            code, text, calls = self.invoke(source, target, status, key='')
            self.assertEqual((code, calls), (1, 0))
            record = json.loads(status.read_text())
            self.assertEqual(record['stage'], 'CONFIGURATION')
            self.assertEqual(record['attempted_calls'], 0)
            self.assertEqual(record['error_code'], 'OPENAI_API_KEY_REQUIRED')
            code, text, calls = self.invoke(source, target, source)
            self.assertEqual((code, calls), (1, 0))
            self.assertEqual(source.read_text(), original)
            self.assertIn('DIAGNOSTIC_PATH_ALIAS', text)

    def test_unknown_error_text_and_invalid_status_are_never_rendered(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target, status = [Path(directory)/n for n in ('source.json', 'meeting.json', 'status.json')]
            source.write_text(json.dumps(current_bundle()))
            code, text, calls = self.invoke(source, target, status, responses=[ValueError('secret-key arbitrary provider body')])
            self.assertEqual((code, calls), (1, 1))
            self.assertNotIn('secret-key', text+status.read_text())
            record = json.loads(status.read_text())
            self.assertEqual(record['error_code'], 'INPUT_OR_VALIDATION_ERROR')
            for mutation in ({'error_code': 'secret-key'}, {'agent': 'secret-key'},
                             {'attempted_calls': True}, {'extra': 'secret-key'}):
                invalid = {**record, **mutation}
                status.write_text(json.dumps(invalid))
                summary = read_summary(status)
                self.assertIn('유효한 실행 진단 없음', summary)
                self.assertNotIn('secret-key', summary)
            status.write_bytes(b'x'*8193)
            self.assertIn('유효한 실행 진단 없음', read_summary(status))
            status.unlink()
            self.assertIn('유효한 실행 진단 없음', read_summary(status))


if __name__ == '__main__':
    unittest.main()
