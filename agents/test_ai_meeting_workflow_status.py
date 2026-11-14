from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_meeting_workflow_status import read_status, write_status, protect_status_path, WorkflowStatusRecorder, PLAN

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
EVENT = {'version': 'MEETING_WORKFLOW_EVENT_1', 'event': 'STAGE_STARTED',
         'workflow_stage': 'PREPARATION', 'status': 'RUNNING'}


class WorkflowStatusTests(unittest.TestCase):
    def test_roundtrip_and_terminal_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'status.json'
            write_status(EVENT, path, 'a'*32, now=NOW)
            value = read_status(path, now=NOW, expected_execution_id='a'*32)
            self.assertEqual(value['workflow_stage'], 'PREPARATION')
            event = {**EVENT, 'event': 'WORKFLOW_FINISHED', 'workflow_stage': 'SETUP', 'status': 'READY_NO_MODEL_CALLS'}
            write_status(event, path, 'a'*32, now=NOW)
            self.assertEqual(read_status(path, now=NOW)['status'], 'READY_NO_MODEL_CALLS')
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_stale_future_and_different_execution_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'status.json'
            write_status(EVENT, path, 'a'*32, now=NOW)
            for now in [NOW+timedelta(seconds=301), NOW-timedelta(seconds=1)]:
                with self.assertRaises(ValueError):
                    read_status(path, now=now)
            with self.assertRaises(ValueError):
                read_status(path, now=NOW, expected_execution_id='b'*32)

    def test_untrusted_or_oversized_snapshots_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'status.json'
            write_status(EVENT, path, 'a'*32, now=NOW)
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                write_status({**EVENT, 'secret': 'must not persist'}, path, 'a'*32, now=NOW)
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(ValueError):
                write_status({**EVENT, 'status': 'COMPLETED'}, path, 'a'*32, now=NOW)
            path.write_bytes(b'x'*4097)
            with self.assertRaises(ValueError):
                read_status(path, now=NOW)

    def test_model_progress_roles_counts_and_versions_are_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'status.json'
            event = {'version': 'MEETING_WORKFLOW_EVENT_2', 'event': 'MODEL_PROGRESS',
                     'workflow_stage': 'INFERENCE', 'status': 'RUNNING', 'agent': 'QUANT',
                     'phase': 'PEER_REVIEW', 'attempted_calls': 5, 'validated_responses': 4}
            write_status(event, path, 'a'*32, now=NOW)
            value = read_status(path, now=NOW)
            self.assertEqual(value['version'], 'MEETING_WORKFLOW_STATUS_2')
            self.assertEqual(value['agent'], 'QUANT')
            original = path.read_bytes()
            for update in [{'agent': 'COMMANDER'}, {'phase': 'ANALYSIS'},
                           {'validated_responses': 1}, {'attempted_calls': True},
                           {'validated_responses': 6}, {'attempted_calls': 8},
                           {'workflow_stage': 'COMPLETED'}, {'status': 'COMPLETED'}]:
                with self.assertRaises(ValueError):
                    write_status({**event, **update}, path, 'a'*32, now=NOW)
                self.assertEqual(path.read_bytes(), original)

    def test_status_alias_cannot_overwrite_inputs_or_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory)/'source.json', Path(directory)/'target.json'
            source.write_bytes(b'source');target.write_bytes(b'target')
            hard, link = Path(directory)/'hard.json', Path(directory)/'link.json'
            os.link(source, hard);link.symlink_to(target)
            for path in [source, target, hard, link]:
                with self.assertRaises(ValueError):
                    protect_status_path(path, source, target)
            self.assertEqual(source.read_bytes(), b'source')
            self.assertEqual(target.read_bytes(), b'target')


class RecorderTests(unittest.TestCase):
    def stage(self, name, *, status='RUNNING'):
        return {'version': 'MEETING_WORKFLOW_EVENT_1', 'event': 'STAGE_STARTED' if status == 'RUNNING' else 'WORKFLOW_FINISHED',
                'workflow_stage': name, 'status': status}

    def progress(self, attempted, validated):
        agent, phase = PLAN[attempted-1]
        return {'version': 'MEETING_WORKFLOW_EVENT_2', 'event': 'MODEL_PROGRESS',
                'workflow_stage': 'INFERENCE', 'status': 'RUNNING', 'agent': agent,
                'phase': phase, 'attempted_calls': attempted, 'validated_responses': validated}

    def start(self, recorder):
        for name in WorkflowStatusRecorder.ORDER[:5]:
            recorder(self.stage(name))

    def test_complete_sequence_cannot_restart_after_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'status.json'
            recorder = WorkflowStatusRecorder(path, 'a'*32, clock=lambda: NOW)
            self.start(recorder)
            for attempted in range(1, 8):
                recorder(self.progress(attempted, attempted-1))
                recorder(self.progress(attempted, attempted))
            recorder(self.stage('PUBLICATION'))
            recorder(self.stage('COMPLETED', status='COMPLETED'))
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                recorder(self.stage('INPUT'))
            self.assertEqual(path.read_bytes(), before)

    def test_regression_skipped_counts_and_early_publication_preserve_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'status.json'
            recorder = WorkflowStatusRecorder(path, 'a'*32, clock=lambda: NOW)
            self.start(recorder)
            recorder(self.progress(1, 0));recorder(self.progress(1, 1))
            before = path.read_bytes()
            for event in [self.stage('SETUP'), self.progress(1, 0), self.progress(3, 2),
                          self.stage('PUBLICATION'), self.stage('INFERENCE')]:
                with self.assertRaises(ValueError):
                    recorder(event)
                self.assertEqual(path.read_bytes(), before)
            recorder(self.progress(2, 1))
            self.assertEqual(read_status(path, now=NOW)['attempted_calls'], 2)

    def test_clock_and_write_failures_do_not_advance_recorder(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'status.json'
            clock = [NOW]
            recorder = WorkflowStatusRecorder(path, 'a'*32, clock=lambda: clock[0])
            recorder(self.stage('INPUT'))
            before = path.read_bytes()
            clock[0] = NOW-timedelta(seconds=1)
            with self.assertRaises(ValueError):
                recorder(self.stage('PREPARATION'))
            clock[0] = NOW
            with patch('ai_meeting_workflow_status.publish_report', side_effect=OSError('private')):
                with self.assertRaises(OSError):
                    recorder(self.stage('PREPARATION'))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(recorder.previous['workflow_stage'], 'INPUT')
            recorder(self.stage('PREPARATION'))
            self.assertEqual(recorder.previous['workflow_stage'], 'PREPARATION')

    def test_real_fixture_workflow_uses_ordered_recorder(self):
        from ai_meeting_workflow import run_workflow
        from test_ai_meeting_runtime import Fixture
        from test_v233_agent_research_runtime import source
        with tempfile.TemporaryDirectory() as directory:
            brief, target, path = [Path(directory)/name for name in ('brief.json', 'transcript.json', 'status.json')]
            payload = source();now = datetime.now(timezone.utc)
            payload['source_generated_at_utc'] = (now-timedelta(minutes=10)).isoformat()
            payload['generated_at_utc'] = (now-timedelta(minutes=5)).isoformat()
            brief.write_text(json.dumps(payload))
            recorder = WorkflowStatusRecorder(path, 'a'*32)
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'private-fixture-key'}):
                with patch('ai_meeting_workflow.OpenAIProvider', return_value=Fixture()):
                    result = run_workflow(brief, target, 'test-model', enable_live=True, on_event=recorder)
            self.assertEqual(result['status'], 'COMPLETED')
            self.assertEqual(result['model_calls_performed'], 0)
            self.assertEqual(recorder.counts, (7, 7))
            self.assertEqual(read_status(path)['status'], 'COMPLETED')
            self.assertNotIn('private-fixture-key', path.read_text())


if __name__ == '__main__':
    unittest.main()
