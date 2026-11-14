"""Bounded local workflow snapshots. No prompts, credentials or trading state."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from ai_meeting_runtime import publish_report

STAGES = {'INPUT', 'PREPARATION', 'SETUP', 'CONFIGURATION', 'INFERENCE', 'PUBLICATION', 'COMPLETED'}
PROGRESS_FIELDS = {'agent', 'phase', 'attempted_calls', 'validated_responses'}
PLAN = [(agent, 'ANALYSIS') for agent in ('ATLAS', 'QUANT', 'GUARDIAN')] + [(agent, 'PEER_REVIEW') for agent in ('ATLAS', 'QUANT', 'GUARDIAN')] + [('COMMANDER', 'CONCLUSION')]
FIELDS = {'version', 'event', 'workflow_stage', 'status', 'execution_id', 'updated_at_utc'}


def validate_status(value, *, now=None, expected_execution_id=None):
    now = now or datetime.now(timezone.utc)
    extended = isinstance(value, dict) and value.get('version') == 'MEETING_WORKFLOW_STATUS_2'
    if not isinstance(value, dict) or set(value) != (FIELDS | PROGRESS_FIELDS if extended else FIELDS) or value['version'] not in ('MEETING_WORKFLOW_STATUS_1', 'MEETING_WORKFLOW_STATUS_2'):
        raise ValueError('INVALID_STATUS_FIELDS')
    if not isinstance(value['execution_id'], str) or not re.fullmatch('[a-f0-9]{32}', value['execution_id']):
        raise ValueError('INVALID_EXECUTION_ID')
    if expected_execution_id is not None and value['execution_id'] != expected_execution_id:
        raise ValueError('DIFFERENT_EXECUTION')
    if not isinstance(value['updated_at_utc'], str):
        raise ValueError('INVALID_STATUS_TIME')
    updated = datetime.fromisoformat(value['updated_at_utc'])
    if now.tzinfo is None or updated.tzinfo is None or not 0 <= (now-updated).total_seconds() <= 300:
        raise ValueError('STALE_OR_FUTURE_STATUS')
    stage, status, event = value['workflow_stage'], value['status'], value['event']
    if not isinstance(stage, str) or stage not in STAGES:
        raise ValueError('INVALID_STAGE')
    valid = ((status == 'RUNNING' and event == 'STAGE_STARTED' and stage != 'COMPLETED') or
             (status == 'READY_NO_MODEL_CALLS' and event == 'WORKFLOW_FINISHED' and stage == 'SETUP') or
             (status == 'COMPLETED' and event == 'WORKFLOW_FINISHED' and stage == 'COMPLETED') or
             (status == 'BLOCKED' and event == 'WORKFLOW_FINISHED' and stage != 'COMPLETED'))
    if extended:
        attempted, validated = value['attempted_calls'], value['validated_responses']
        valid = (status == 'RUNNING' and event == 'MODEL_PROGRESS' and stage == 'INFERENCE'
                 and type(attempted) is int and type(validated) is int
                 and 1 <= attempted <= 7 and 0 <= validated <= attempted
                 and attempted-validated <= 1)
        if valid:
            valid = (value['agent'], value['phase']) == PLAN[attempted-1]
    if not valid:
        raise ValueError('INCONSISTENT_STATUS')
    return dict(value)


def write_status(event, path, execution_id, *, now=None):
    extended = isinstance(event, dict) and event.get('version') == 'MEETING_WORKFLOW_EVENT_2'
    expected = {'version', 'event', 'workflow_stage', 'status'} | (PROGRESS_FIELDS if extended else set())
    if not isinstance(event, dict) or set(event) != expected or event['version'] not in ('MEETING_WORKFLOW_EVENT_1', 'MEETING_WORKFLOW_EVENT_2'):
        raise ValueError('INVALID_EVENT')
    now = now or datetime.now(timezone.utc)
    value = {**event, 'version': 'MEETING_WORKFLOW_STATUS_2' if extended else 'MEETING_WORKFLOW_STATUS_1',
             'execution_id': execution_id, 'updated_at_utc': now.isoformat()}
    publish_report(validate_status(value, now=now), path)


def read_status(path, *, now=None, expected_execution_id=None):
    with Path(path).open('rb') as stream:
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise ValueError('STATUS_TOO_LARGE')
    return validate_status(json.loads(raw), now=now, expected_execution_id=expected_execution_id)


def protect_status_path(path, source, destination):
    path = Path(path)
    for protected in (Path(source), Path(destination)):
        if path.resolve() == protected.resolve() or (path.exists() and protected.exists() and path.samefile(protected)):
            raise ValueError('STATUS_PATH_ALIAS')
