"""Local brief-to-meeting workflow; check-only unless live execution is explicit."""
import argparse
import json
import re
import sys
from pathlib import Path
import tempfile
import uuid

from ai_meeting_workflow_status import protect_status_path, WorkflowStatusRecorder

from ai_meeting_prepare import prepare_file
from ai_meeting_setup import check_setup
from ai_meeting_runtime import (MeetingError, OpenAIProvider, publish_report,
                                run_meeting, safe_error_code)


def run_workflow(source, destination, model, *, enable_live=False, progress=None, on_event=None, execution_id=None):
    stage, attempted = 'INPUT', False

    def enter(name):
        nonlocal stage
        stage = name
        if on_event:
            on_event({'version': 'MEETING_WORKFLOW_EVENT_1', 'event': 'STAGE_STARTED',
                      'workflow_stage': name, 'status': 'RUNNING'})

    def finish(result):
        if on_event:
            on_event({'version': 'MEETING_WORKFLOW_EVENT_1', 'event': 'WORKFLOW_FINISHED',
                      'workflow_stage': result['workflow_stage'], 'status': result['status']})
        return result

    try:
        enter('INPUT')
        if execution_id is not None and (not isinstance(execution_id, str) or not re.fullmatch('[a-f0-9]{32}', execution_id)):
            raise MeetingError('INVALID_EXECUTION_ID')
        if type(enable_live) is not bool:
            raise ValueError('INVALID_EXECUTION_SWITCH')
        source, destination = Path(source), Path(destination)
        if (source.resolve() == destination.resolve() or
                (source.exists() and destination.exists() and source.samefile(destination))):
            raise MeetingError('SOURCE_DESTINATION_ALIAS')
        with tempfile.TemporaryDirectory(prefix='spacebar-meeting-') as directory:
            bundle_path = Path(directory)/'bundle.json'
            enter('PREPARATION')
            prepared = prepare_file(source, bundle_path)
            if prepared['status'] != 'BUNDLE_PREPARED':
                return finish({**prepared, 'workflow_stage': stage})
            enter('SETUP')
            checked = check_setup(bundle_path, model)
            if checked['status'] != 'LOCAL_SETUP_VALID':
                return finish({**checked, 'workflow_stage': stage})
            if not enable_live:
                return finish({**checked, 'status': 'READY_NO_MODEL_CALLS', 'workflow_stage': stage})
            enter('CONFIGURATION')
            provider = OpenAIProvider(enabled=True, model=model)
            bundle = json.loads(bundle_path.read_text(encoding='utf-8'))
            enter('INFERENCE')
            attempted = True
            def runtime_progress(event):
                if on_event:
                    on_event({'version': 'MEETING_WORKFLOW_EVENT_2', 'event': 'MODEL_PROGRESS',
                              'workflow_stage': 'INFERENCE', 'status': 'RUNNING',
                              **{key: event[key] for key in ('agent', 'phase', 'attempted_calls', 'validated_responses')}})
                if progress:
                    progress(event)
            report = run_meeting(bundle, provider, progress=runtime_progress)
            if execution_id is not None:
                report['workflow_execution_id'] = execution_id
            enter('PUBLICATION')
            publish_report(report, destination)
            return finish({'status': 'COMPLETED', 'workflow_stage': 'COMPLETED',
                    'model_calls_performed': report['call_count'] if report['model_inference_performed'] else 0,
                    'validated_responses': report['call_count'],
                    'model_inference_performed': report['model_inference_performed'],
                    'orders_enabled': False, 'error_code': None})
    except (ValueError, OSError, TypeError, KeyError) as error:
        return finish({'status': 'BLOCKED', 'workflow_stage': stage,
                'error_code': safe_error_code(error),
                'model_calls_performed': None if attempted else 0,
                'orders_enabled': False})


def main():
    parser = argparse.ArgumentParser(description='Prepare and check a meeting; no model calls by default')
    parser.add_argument('source', help='Local V229 brief JSON')
    parser.add_argument('destination', help='Completed transcript path; untouched in default check-only mode')
    parser.add_argument('--model', required=True)
    parser.add_argument('--enable-live', action='store_true', help='Authorize up to seven paid model calls')
    parser.add_argument("--json", action="store_true", dest="json_output", help="Print only the final JSON result to stdout; notices/progress go to stderr")
    parser.add_argument("--events", action="store_true", help="Emit structured workflow stage events to stderr")
    parser.add_argument("--status-file", type=Path, help="Atomically record the latest local workflow stage")
    args = parser.parse_args()
    execution_id = uuid.uuid4().hex
    recorder = WorkflowStatusRecorder(args.status_file, execution_id) if args.status_file else None
    notice_stream = sys.stderr if args.json_output else sys.stdout
    if args.enable_live:
        print('Live research requested: up to seven paid calls; no orders.', file=notice_stream, flush=True)
    def progress(event):
        print(json.dumps({'agent': event['agent'], 'phase': event['phase'],
                          'event': event['event'], 'validated_responses': event['validated_responses']}), file=notice_stream, flush=True)
    def workflow_event(event):
        if args.status_file:
            recorder(event)
        if args.events:
            print(json.dumps(event), file=sys.stderr, flush=True)
    started = False
    try:
        if args.status_file:
            protect_status_path(args.status_file, args.source, args.destination)
        started = True
        result = run_workflow(args.source, args.destination, args.model,
                              enable_live=args.enable_live, progress=progress,
                              on_event=workflow_event if args.events or args.status_file else None,
                              execution_id=execution_id)
    except (OSError, ValueError, TypeError, KeyError):
        # A status observer can fail even after inference/publication. Do not claim zero use.
        result = {'status': 'BLOCKED', 'workflow_stage': 'STATUS_RECORDING',
                  'error_code': 'STATUS_RECORDING_FAILED', 'model_calls_performed': None if started else 0,
                  'orders_enabled': False}
    result = {**result, "execution_id": execution_id}
    print(json.dumps(result, ensure_ascii=False))
    if result['status'] == 'READY_NO_MODEL_CALLS':
        print('Local checks only; API access, billing and model compatibility remain unverified.', file=notice_stream)
    return 0 if result['status'] in ('READY_NO_MODEL_CALLS', 'COMPLETED') else 1


if __name__ == '__main__':
    raise SystemExit(main())
