"""Local brief-to-meeting workflow; check-only unless live execution is explicit."""
import argparse
import json
from pathlib import Path
import tempfile

from ai_meeting_prepare import prepare_file
from ai_meeting_setup import check_setup
from ai_meeting_runtime import (MeetingError, OpenAIProvider, publish_report,
                                run_meeting, safe_error_code)


def run_workflow(source, destination, model, *, enable_live=False, progress=None):
    stage, attempted = 'INPUT', False
    try:
        if type(enable_live) is not bool:
            raise ValueError('INVALID_EXECUTION_SWITCH')
        source, destination = Path(source), Path(destination)
        if (source.resolve() == destination.resolve() or
                (source.exists() and destination.exists() and source.samefile(destination))):
            raise MeetingError('SOURCE_DESTINATION_ALIAS')
        with tempfile.TemporaryDirectory(prefix='spacebar-meeting-') as directory:
            bundle_path = Path(directory)/'bundle.json'
            stage = 'PREPARATION'
            prepared = prepare_file(source, bundle_path)
            if prepared['status'] != 'BUNDLE_PREPARED':
                return {**prepared, 'workflow_stage': stage}
            stage = 'SETUP'
            checked = check_setup(bundle_path, model)
            if checked['status'] != 'LOCAL_SETUP_VALID':
                return {**checked, 'workflow_stage': stage}
            if not enable_live:
                return {**checked, 'status': 'READY_NO_MODEL_CALLS', 'workflow_stage': stage}
            stage = 'CONFIGURATION'
            provider = OpenAIProvider(enabled=True, model=model)
            bundle = json.loads(bundle_path.read_text(encoding='utf-8'))
            stage, attempted = 'INFERENCE', True
            report = run_meeting(bundle, provider, progress=progress)
            stage = 'PUBLICATION'
            publish_report(report, destination)
            return {'status': 'COMPLETED', 'workflow_stage': 'COMPLETED',
                    'model_calls_performed': report['call_count'] if report['model_inference_performed'] else 0,
                    'validated_responses': report['call_count'],
                    'model_inference_performed': report['model_inference_performed'],
                    'orders_enabled': False, 'error_code': None}
    except (ValueError, OSError, TypeError, KeyError) as error:
        return {'status': 'BLOCKED', 'workflow_stage': stage,
                'error_code': safe_error_code(error),
                'model_calls_performed': None if attempted else 0,
                'orders_enabled': False}


def main():
    parser = argparse.ArgumentParser(description='Prepare and check a meeting; no model calls by default')
    parser.add_argument('source', help='Local V229 brief JSON')
    parser.add_argument('destination', help='Completed transcript path; untouched in default check-only mode')
    parser.add_argument('--model', required=True)
    parser.add_argument('--enable-live', action='store_true', help='Authorize up to seven paid model calls')
    args = parser.parse_args()
    if args.enable_live:
        print('Live research requested: up to seven paid calls; no orders.', flush=True)
    def progress(event):
        print(json.dumps({'agent': event['agent'], 'phase': event['phase'],
                          'event': event['event'], 'validated_responses': event['validated_responses']}), flush=True)
    result = run_workflow(args.source, args.destination, args.model,
                          enable_live=args.enable_live, progress=progress)
    print(json.dumps(result, ensure_ascii=False))
    if result['status'] == 'READY_NO_MODEL_CALLS':
        print('Local checks only; API access, billing and model compatibility remain unverified.')
    return 0 if result['status'] in ('READY_NO_MODEL_CALLS', 'COMPLETED') else 1


if __name__ == '__main__':
    raise SystemExit(main())
