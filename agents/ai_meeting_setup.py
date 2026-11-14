"""Local setup check; no network, inference, publication or orders."""
import argparse
import json
from pathlib import Path

from ai_meeting_runtime import MeetingError, OpenAIProvider, safe_error_code
from provider_transport_preflight_v240 import preflight


def check_setup(source, model, *, now=None):
    """Validate bounded input and local configuration without calling a provider."""
    try:
        with Path(source).open('rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise MeetingError('SOURCE_TOO_LARGE')
        bundle = json.loads(raw)
        preflight(bundle, dry_run=True, now=now)
        # Construction checks model/key presence only. complete() is never called.
        OpenAIProvider(enabled=True, model=model)
    except (ValueError, OSError, TypeError, KeyError) as error:
        return {'status': 'BLOCKED', 'error_code': safe_error_code(error),
                'model_calls_performed': 0, 'provider_verified': False,
                'orders_enabled': False}
    return {'status': 'LOCAL_SETUP_VALID', 'error_code': None,
            'model_calls_performed': 0, 'provider_verified': False,
            'orders_enabled': False}


def main():
    parser = argparse.ArgumentParser(description='Check meeting inputs and local configuration without API calls')
    parser.add_argument('source', type=Path, help='Existing V236 request bundle')
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    result = check_setup(args.source, args.model)
    print(json.dumps(result, ensure_ascii=False))
    print('Local checks only; API access, billing, model support and output quality are not verified.')
    return 0 if result['status'] == 'LOCAL_SETUP_VALID' else 1


if __name__ == '__main__':
    raise SystemExit(main())
