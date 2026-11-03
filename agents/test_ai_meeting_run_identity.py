from contextlib import redirect_stdout, redirect_stderr
from datetime import timedelta
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_meeting_diagnostics import read_summary, render_status
from ai_meeting_runtime import main, OpenAIProvider
from test_ai_meeting_runtime import statement
from test_ai_meeting_diagnostics import current_bundle
from test_v233_agent_research_runtime import NOW


class RunIdentityTests(unittest.TestCase):
    def record(self):
        return {'version': 'MEETING_DIAGNOSTICS_2', 'execution_id': '12345-1',
                'started_at_utc': (NOW-timedelta(minutes=1)).isoformat(), 'updated_at_utc': NOW.isoformat(),
                'status': 'COMPLETED', 'stage': 'COMPLETED', 'agent': 'COMMANDER',
                'phase': 'CONCLUSION', 'attempted_calls': 7, 'validated_responses': 7, 'error_code': None}

    def test_unbound_old_completed_record_is_not_accepted_as_current_diagnostic(self):
        old = {'version': 'MEETING_DIAGNOSTICS_1', 'status': 'COMPLETED', 'stage': 'COMPLETED',
               'agent': 'COMMANDER', 'phase': 'CONCLUSION', 'attempted_calls': 7,
               'validated_responses': 7, 'error_code': None}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'status.json'
            path.write_text(json.dumps(old))
            self.assertIn('유효한 실행 진단 없음', read_summary(path))

    def test_exact_workflow_run_and_attempt_are_required_even_for_fresh_success(self):
        record = self.record()
        self.assertIn('회의 파일 생성 완료', render_status(record, expected_execution_id='12345-1', now=NOW))
        for expected in ('12345-2', '12346-1', 'sensitive-invalid-input'):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                render_status(record, expected_execution_id=expected, now=NOW)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'status.json'
            path.write_text(json.dumps(record))
            text = read_summary(path, expected_execution_id='12345-2', now=NOW)
            self.assertIn('유효한 실행 진단 없음', text)
            self.assertNotIn('회의 파일 생성 완료', text)

    def test_stale_future_reversed_naive_and_missing_times_are_rejected(self):
        record = self.record()
        render_status(record, now=NOW+timedelta(hours=8))
        with self.assertRaises(ValueError):
            render_status(record, now=NOW+timedelta(hours=8, microseconds=1))
        for change in ({'updated_at_utc': (NOW+timedelta(seconds=1)).isoformat()},
                       {'started_at_utc': (NOW+timedelta(seconds=1)).isoformat()},
                       {'updated_at_utc': '2026-10-31T06:00:00'},
                       {'started_at_utc': None}, {'execution_id': '<script>secret</script>'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                render_status({**record, **change}, now=NOW)

    def run_cli(self, source, target, status, extra=()):
        args = ['meeting', str(source), str(target), '--model', 'test', '--enable-live', '--diagnostics', str(status), *extra]
        output = io.StringIO()
        with patch('sys.argv', args), patch.dict(os.environ, {'OPENAI_API_KEY': 'test-secret'}), \
                patch.object(OpenAIProvider, 'complete', return_value=statement()) as complete, \
                redirect_stdout(output), redirect_stderr(output):
            code = 0
            try:
                main()
            except SystemExit as exit:
                code = exit.code
        return code, output.getvalue(), complete.call_count

    def test_cli_defaults_to_new_uuid_and_accepts_explicit_workflow_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target, status = [Path(directory)/name for name in ('source.json', 'meeting.json', 'status.json')]
            source.write_text(json.dumps(current_bundle()))
            ids = []
            for _ in range(2):
                code, output, calls = self.run_cli(source, target, status)
                self.assertEqual((code, calls), (0, 7))
                record = json.loads(status.read_text())
                ids.append(record['execution_id'])
                self.assertEqual(record['version'], 'MEETING_DIAGNOSTICS_2')
                self.assertNotIn('test-secret', output+status.read_text())
                self.assertIn('회의 파일 생성 완료', read_summary(status, expected_execution_id=ids[-1]))
            self.assertNotEqual(*ids)
            self.assertIn('유효한 실행 진단 없음', read_summary(status, expected_execution_id=ids[0]))
            self.assertEqual(self.run_cli(source, target, status, ('--execution-id', '12345-2'))[0], 0)
            self.assertEqual(json.loads(status.read_text())['execution_id'], '12345-2')

    def test_invalid_execution_id_stops_before_provider_and_does_not_echo_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target, status = [Path(directory)/name for name in ('source.json', 'meeting.json', 'status.json')]
            source.write_text(json.dumps(current_bundle()))
            target.write_text('previous completed transcript')
            code, output, calls = self.run_cli(source, target, status, ('--execution-id', 'sensitive-secret-input'))
            self.assertEqual((code, calls), (1, 0))
            self.assertIn('INVALID_EXECUTION_ID', output)
            self.assertNotIn('sensitive-secret-input', output)
            self.assertFalse(status.exists())
            self.assertEqual(target.read_text(), 'previous completed transcript')

    def test_workflow_passes_same_identity_to_runtime_and_always_summary(self):
        workflow = (Path(__file__).resolve().parent.parent/'.github/workflows/run_ai_meeting.yml').read_text()
        identity = 'SPACEBAR_MEETING_EXECUTION_ID: ${{ github.run_id }}-${{ github.run_attempt }}'
        self.assertEqual(workflow.count(identity), 2)
        self.assertIn('--execution-id "$SPACEBAR_MEETING_EXECUTION_ID"', workflow)
        self.assertIn('--expected-execution-id "$SPACEBAR_MEETING_EXECUTION_ID"', workflow)


if __name__ == '__main__':
    unittest.main()
