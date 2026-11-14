from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest

from ai_meeting_workflow_status import read_status, write_status, protect_status_path

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
