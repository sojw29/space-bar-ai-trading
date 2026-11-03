from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from ai_meeting_diagnostics import render_status, read_summary
from ai_meeting_runtime import run_meeting, MeetingError
from test_ai_meeting_runtime import Fixture, statement
from test_v240_provider_transport_preflight import request
from test_v233_agent_research_runtime import NOW


def record(**changes):
    value = {'version': 'MEETING_DIAGNOSTICS_2', 'execution_id': '12345-1',
             'started_at_utc': (NOW-timedelta(minutes=1)).isoformat(), 'updated_at_utc': NOW.isoformat(),
             'status': 'COMPLETED', 'stage': 'COMPLETED', 'agent': 'COMMANDER',
             'phase': 'CONCLUSION', 'attempted_calls': 7, 'validated_responses': 7, 'error_code': None}
    value.update(changes)
    return value


class StatusConsistencyTests(unittest.TestCase):
    def test_completed_count_with_wrong_role_or_phase_is_rejected(self):
        for change in ({'agent': 'ATLAS'}, {'phase': 'ANALYSIS'}, {'agent': None, 'phase': None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                render_status(record(**change), now=NOW)

    def test_all_actual_runtime_progress_events_and_final_completion_are_accepted(self):
        snapshots = []
        def observe(event):
            snapshot = record(status='RUNNING', stage='INFERENCE', **{
                name: event[name] for name in ('agent', 'phase', 'attempted_calls', 'validated_responses')})
            render_status(snapshot, now=NOW)
            snapshots.append(snapshot)
        run_meeting(request(), Fixture(), clock=lambda: NOW, progress=observe)
        self.assertEqual(len(snapshots), 14)
        self.assertIn('회의 파일 생성 완료', render_status(record(), now=NOW))
        self.assertNotIn('회의 파일 생성 완료입니다', render_status(snapshots[-1], now=NOW))

    def test_real_partial_failure_and_zero_call_validation_failure_remain_valid(self):
        observed = []
        fixture = Fixture()
        fixture.complete = Mock(side_effect=[statement(), MeetingError('PROVIDER_TIMEOUT')])
        with self.assertRaises(MeetingError):
            run_meeting(request(), fixture, clock=lambda: NOW, progress=observed.append)
        failed = record(status='FAILED', stage='INFERENCE', error_code='PROVIDER_TIMEOUT', **{
            name: observed[-1][name] for name in ('agent', 'phase', 'attempted_calls', 'validated_responses')})
        self.assertIn('PROVIDER_TIMEOUT', render_status(failed, now=NOW))
        for stage in ('INPUT', 'CONFIGURATION', 'INFERENCE'):
            render_status(record(status='FAILED', stage=stage, agent=None, phase=None,
                                 attempted_calls=0, validated_responses=0,
                                 error_code='INPUT_OR_VALIDATION_ERROR'), now=NOW)
        # Freshness can fail between calls after the previous response was validated.
        render_status(record(status='FAILED', stage='INFERENCE', agent='ATLAS', phase='ANALYSIS',
                             attempted_calls=1, validated_responses=1,
                             error_code='INPUT_OR_VALIDATION_ERROR'), now=NOW)

    def test_skipped_responses_impossible_stage_and_inconsistent_completion_are_rejected(self):
        cases = [dict(status='RUNNING', stage='INFERENCE', attempted_calls=5, validated_responses=1,
                      agent='QUANT', phase='PEER_REVIEW'),
                 dict(stage='INPUT'), dict(stage='CONFIGURATION'),
                 dict(status='RUNNING'),
                 dict(status='FAILED', error_code='FILE_ERROR'),
                 dict(status='RUNNING', stage='PUBLICATION', attempted_calls=6, validated_responses=6,
                      agent='GUARDIAN', phase='PEER_REVIEW'),
                 dict(status='RUNNING', stage='INFERENCE', attempted_calls=0, validated_responses=0),
                 dict(status='RUNNING', stage='INFERENCE', attempted_calls=2, validated_responses=1,
                      agent='QUANT', phase='PEER_REVIEW')]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                render_status(record(**change), now=NOW)

    def test_publishing_complete_responses_does_not_claim_file_creation_success(self):
        for status, code in (('RUNNING', None), ('FAILED', 'FILE_ERROR')):
            summary = render_status(record(status=status, stage='PUBLICATION', error_code=code), now=NOW)
            self.assertNotIn('회의 파일 생성 완료입니다', summary)
            self.assertIn('회의 완료나 공개 게시 성공을 의미하지 않습니다', summary)

    def test_inconsistent_record_falls_back_without_success_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'diagnostic.json'
            path.write_text(json.dumps(record(agent='ATLAS')))
            summary = read_summary(path, now=NOW, expected_execution_id='12345-1')
            self.assertIn('유효한 실행 진단 없음', summary)
            self.assertNotIn('회의 파일 생성 완료입니다', summary)


if __name__ == '__main__':
    unittest.main()
