from contextlib import redirect_stdout, redirect_stderr
from http.client import IncompleteRead, BadStatusLine, RemoteDisconnected, HTTPException
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_meeting_runtime import OpenAIProvider, MeetingError, main
from ai_meeting_diagnostics import read_summary
from test_ai_meeting_diagnostics import current_bundle
from test_ai_meeting_runtime import statement


class InterruptedTransportTests(unittest.TestCase):
    def test_incomplete_response_is_converted_to_safe_meeting_error(self):
        with patch('ai_meeting_runtime.build_opener') as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.read.side_effect = IncompleteRead(b'private response fragment', 100)
            provider = OpenAIProvider(enabled=True, model='test', api_key='test-secret')
            with self.assertRaisesRegex(MeetingError, '^PROVIDER_CONNECTION_INTERRUPTED$'):
                provider.complete('ATLAS', 'ANALYSIS', {})
            opener.return_value.open.assert_called_once()
            opener.return_value.open.return_value.__exit__.assert_called_once()

    def response(self):
        return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps(statement()), 'refusal': None}}]}).encode()

    def test_connection_status_line_and_cleanup_errors_are_redacted_without_retry(self):
        cases = [('open', RemoteDisconnected('private server detail')),
                 ('read', BadStatusLine('private server detail')),
                 ('exit', HTTPException('private server detail'))]
        for phase, error in cases:
            with self.subTest(phase=phase), patch('ai_meeting_runtime.build_opener') as opener:
                context = opener.return_value.open.return_value
                context.__enter__.return_value.read.return_value = self.response()
                if phase == 'open': opener.return_value.open.side_effect = error
                elif phase == 'read': context.__enter__.return_value.read.side_effect = error
                else: context.__exit__.side_effect = error
                with self.assertRaises(MeetingError) as raised:
                    OpenAIProvider(enabled=True, model='test', api_key='test-secret').complete('ATLAS', 'ANALYSIS', {})
                self.assertEqual(str(raised.exception), 'PROVIDER_CONNECTION_INTERRUPTED')
                self.assertIsNone(raised.exception.__cause__)
                self.assertTrue(raised.exception.__suppress_context__)
                self.assertEqual(opener.return_value.open.call_count, 1)

    def test_interruption_at_first_middle_or_final_call_records_failure_and_preserves_output(self):
        for completed in (0, 1, 6):
            with self.subTest(completed=completed), tempfile.TemporaryDirectory() as directory:
                source, target, status = [Path(directory)/name for name in ('source.json', 'meeting.json', 'status.json')]
                source.write_text(json.dumps(current_bundle()))
                target.write_text('previous completed transcript')
                args = ['meeting', str(source), str(target), '--enable-live', '--model', 'test',
                        '--diagnostics', str(status), '--execution-id', '12345-1']
                output = io.StringIO()
                with patch('sys.argv', args), patch.dict(os.environ, {'OPENAI_API_KEY': 'test-secret'}), \
                        patch('ai_meeting_runtime.build_opener') as opener, \
                        redirect_stdout(output), redirect_stderr(output):
                    context = opener.return_value.open.return_value
                    context.__enter__.return_value.read.side_effect = [self.response()]*completed + [IncompleteRead(b'private fragment', 100)]
                    with self.assertRaises(SystemExit) as exit:
                        main()
                    self.assertEqual(exit.exception.code, 1)
                    self.assertEqual(opener.return_value.open.call_count, completed+1)
                    self.assertEqual(context.__exit__.call_count, completed+1)
                self.assertEqual(target.read_text(), 'previous completed transcript')
                record = json.loads(status.read_text())
                self.assertEqual(record['status'], 'FAILED')
                self.assertEqual(record['stage'], 'INFERENCE')
                self.assertEqual(record['error_code'], 'PROVIDER_CONNECTION_INTERRUPTED')
                self.assertEqual((record['attempted_calls'], record['validated_responses']), (completed+1, completed))
                summary = read_summary(status, expected_execution_id='12345-1')
                self.assertIn('PROVIDER_CONNECTION_INTERRUPTED', summary)
                self.assertNotIn('회의 파일 생성 완료입니다', summary)
                for private in ('private fragment', 'test-secret', 'Traceback', 'IncompleteRead'):
                    self.assertNotIn(private, output.getvalue()+status.read_text()+summary)

    def test_first_call_disconnect_does_not_create_a_completed_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target, status = [Path(directory)/name for name in ('source.json', 'meeting.json', 'status.json')]
            source.write_text(json.dumps(current_bundle()))
            with patch('sys.argv', ['meeting', str(source), str(target), '--enable-live', '--model', 'test', '--diagnostics', str(status)]), \
                    patch.dict(os.environ, {'OPENAI_API_KEY': 'test-secret'}), \
                    patch('ai_meeting_runtime.build_opener') as opener, \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                opener.return_value.open.side_effect = RemoteDisconnected('private detail')
                with self.assertRaises(SystemExit): main()
            self.assertFalse(target.exists())
            self.assertEqual(json.loads(status.read_text())['status'], 'FAILED')


if __name__ == '__main__':
    unittest.main()
