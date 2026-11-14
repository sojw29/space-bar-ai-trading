"""Prepare a runtime input bundle from a local brief, without provider access."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from agent_research_runtime_v233 import build_research
from agent_handoff_audit_v234 import compile_handoff
from research_consistency_review_v235 import review
from model_adapter_contract_v236 import build_adapter_requests
from provider_transport_preflight_v240 import preflight
from ai_meeting_runtime import publish_report, safe_error_code


def prepare_file(source, destination, *, now=None, clock=None):
    stage = 'INPUT'
    try:
        if now is not None and clock is not None:
            raise ValueError('AMBIGUOUS_CLOCK')
        clock = clock or ((lambda: now) if now is not None else lambda: datetime.now(timezone.utc))
        previous = None

        def current_time():
            nonlocal previous
            value = clock()
            if value.tzinfo is None or (previous is not None and value < previous):
                raise ValueError('CLOCK_CHANGED')
            previous = value
            return value

        source, destination = Path(source), Path(destination)
        if (source.resolve() == destination.resolve() or
                (source.exists() and destination.exists() and source.samefile(destination))):
            raise ValueError('PATH_ALIAS')
        with source.open('rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('INPUT_TOO_LARGE')
        value = json.loads(raw)
        for stage, execute in [('SOURCE_VALIDATION', build_research),
                               ('HANDOFF', compile_handoff),
                               ('CONSISTENCY_REVIEW', review),
                               ('MODEL_REQUESTS', build_adapter_requests)]:
            value = execute(value, now=current_time())
        stage = 'PREFLIGHT'
        preflight(value, dry_run=True, now=current_time())
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8')) > 65536:
            raise ValueError('OUTPUT_TOO_LARGE')
        stage = 'PUBLICATION'
        # Revalidate freshness immediately before the atomic write.
        preflight(value, dry_run=True, now=current_time())
        publish_report(value, destination)
    except (ValueError, OSError, TypeError, KeyError) as error:
        return {'status': 'BLOCKED', 'stage': stage, 'error_code': safe_error_code(error),
                'model_calls_performed': 0, 'orders_enabled': False}
    return {'status': 'BUNDLE_PREPARED', 'stage': 'COMPLETED', 'error_code': None,
            'model_calls_performed': 0, 'orders_enabled': False}


def main():
    parser = argparse.ArgumentParser(description='Prepare a local meeting bundle without model calls')
    parser.add_argument('source', help='Existing V229 commander brief JSON')
    parser.add_argument('destination', help='Runtime V236 input bundle destination')
    args = parser.parse_args()
    result = prepare_file(args.source, args.destination)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'BUNDLE_PREPARED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
