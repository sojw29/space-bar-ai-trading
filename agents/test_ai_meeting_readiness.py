from contextlib import redirect_stdout, redirect_stderr
from datetime import timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_meeting_readiness import (assess_readiness, check_file, render_summary,
                                  summary_from_file, main, STAGES)
from test_v233_agent_research_runtime import source, NOW


class ReadinessTests(unittest.TestCase):
    def test_entire_real_preparation_chain_without_provider_or_network(self):
        with patch('socket.socket', side_effect=AssertionError('network forbidden')), \
                patch('ai_meeting_runtime.OpenAIProvider.__init__', side_effect=AssertionError('provider forbidden')):
            report = assess_readiness(source(), now=NOW)
        self.assertEqual(report['status'], 'INPUTS_READY')
        self.assertEqual(report['checks'], [{'stage': stage, 'status': 'PASS'} for stage in STAGES])
        self.assertEqual(report['prepared_agent_count'], 4)
        self.assertEqual(report['model_calls_performed'], 0)
        self.assertFalse(report['provider_verified'])
        summary = render_summary(report, now=NOW)
        self.assertIn('실제 모델 호출: 0회', summary)
        self.assertIn('API 키·모델 접근·과금·실제 추론은 검증하지 않았습니다', summary)

    def test_each_pipeline_stage_is_identified_without_error_text(self):
        functions = ('build_research', 'compile_handoff', 'review', 'build_adapter_requests', 'preflight')
        for index, function in enumerate(functions):
            with self.subTest(stage=STAGES[index]), patch('ai_meeting_readiness.'+function,
                    side_effect=ValueError('sensitive source text')):
                report = assess_readiness(source(), now=NOW)
            self.assertEqual(report['status'], 'BLOCKED')
            self.assertEqual(report['stage'], STAGES[index])
            self.assertEqual(report['checks'][-1]['status'], 'FAIL')
            self.assertEqual(len(report['checks']), index+1)
            self.assertNotIn('sensitive', json.dumps(report)+render_summary(report, now=NOW))

    def test_stale_future_duplicate_and_unsafe_source_are_blocked(self):
        for mode in ('stale', 'future', 'duplicate', 'orders'):
            brief = source()
            if mode == 'stale': brief['source_generated_at_utc'] = (NOW-timedelta(hours=9)).isoformat()
            elif mode == 'future': brief['generated_at_utc'] = (NOW+timedelta(seconds=1)).isoformat()
            elif mode == 'duplicate': brief['markets'][1]['symbol'] = brief['markets'][0]['symbol']
            else: brief['orders_enabled'] = True
            report = assess_readiness(brief, now=NOW)
            self.assertEqual((report['status'], report['stage']), ('BLOCKED', 'SOURCE_VALIDATION'))
            self.assertFalse(report['orders_enabled'])

    def test_input_file_errors_are_bounded_and_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'brief.json'
            self.assertEqual(check_file(path, now=NOW)['error_code'], 'INPUT_UNAVAILABLE')
            for raw, code in ((b'x'*65537, 'INPUT_TOO_LARGE'), (b'secret', 'INVALID_JSON'), (b'\xff', 'INVALID_JSON')):
                path.write_bytes(raw)
                report = check_file(path, now=NOW)
                self.assertEqual(report['error_code'], code)
                self.assertNotIn('secret', json.dumps(report))

    def test_forged_stale_or_incomplete_ready_report_is_not_rendered(self):
        report = assess_readiness(source(), now=NOW)
        mutations = [{'provider_verified': True}, {'model_calls_performed': 1},
                     {'checks': []}, {'prepared_agent_count': True}, {'stage': 'secret'},
                     {'error_code': 'secret'}, {'extra': 'secret'}]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, TypeError)):
                render_summary({**report, **mutation}, now=NOW)
        with self.assertRaises(ValueError):
            render_summary(report, now=NOW+timedelta(hours=9))

    def test_missing_malformed_or_oversized_summary_does_not_claim_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'report.json'
            self.assertIn('유효한 점검 기록 없음', summary_from_file(path))
            for raw in (b'sensitive data', b'x'*16385, b'{}'):
                path.write_bytes(raw)
                summary = summary_from_file(path)
                self.assertIn('유효한 점검 기록 없음', summary)
                self.assertNotIn('sensitive', summary)

    def test_cli_rejects_same_path_and_hardlink_without_changing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'source.json'
            path.write_text('original source')
            alias = Path(directory)/'alias.json'
            alias.hardlink_to(path)
            for target in (path, alias):
                with patch('sys.argv', ['readiness', 'check', str(path), str(target)]), \
                        redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main()
                self.assertEqual(path.read_text(), 'original source')

    def test_cli_blocked_run_writes_diagnostic_and_returns_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path, target = Path(directory)/'missing.json', Path(directory)/'report.json'
            with patch('sys.argv', ['readiness', 'check', str(source_path), str(target)]), \
                    redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as exit:
                main()
            self.assertEqual(exit.exception.code, 1)
            self.assertEqual(json.loads(target.read_text())['error_code'], 'INPUT_UNAVAILABLE')

    def test_readiness_workflow_has_no_provider_secret_or_deployment_path(self):
        flow = (Path(__file__).resolve().parent.parent/'.github/workflows/check_ai_meeting_readiness.yml').read_text()
        self.assertNotIn('secrets.', flow)
        self.assertNotIn('pages: write', flow)
        self.assertNotIn('deploy-pages', flow)
        self.assertNotIn('--enable-live', flow)
        self.assertNotIn('ai_meeting_runtime.py', flow)
        self.assertIn('${{ always() }}', flow)


if __name__ == '__main__':
    unittest.main()
