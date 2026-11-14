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
from ai_meeting_runtime import publish_report


ERROR_GUIDANCE = {
    'AMBIGUOUS_CLOCK': '고정 시각과 시계 함수 중 하나만 지정하세요.',
    'CLOCK_CHANGED': '시계 설정을 확인하고 최신 입력으로 다시 준비하세요.',
    'PATH_ALIAS': '입력과 출력에 서로 다른 파일을 지정하세요.',
    'INPUT_TOO_LARGE': '입력 파일을 64 KiB 이하로 준비하세요.',
    'OUTPUT_TOO_LARGE': '생성된 입력이 실행기 크기 제한을 초과했습니다.',
    'INPUT_UNAVAILABLE': '입력 파일 경로와 읽기 권한을 확인하세요.',
    'INVALID_JSON': '입력 파일의 JSON 형식과 UTF-8 인코딩을 확인하세요.',
    'OUTPUT_WRITE_FAILED': '출력 폴더와 쓰기 권한을 확인하세요.',
    'VALIDATION_FAILED': '실패 단계의 입력 형식·최신성·연구 전용 설정을 확인하세요.',
}


class PreparationError(ValueError):
    pass


def preparation_error_code(error, stage):
    if isinstance(error, PreparationError) and str(error) in ERROR_GUIDANCE:
        return str(error)
    if isinstance(error, OSError):
        return 'OUTPUT_WRITE_FAILED' if stage == 'PUBLICATION' else 'INPUT_UNAVAILABLE'
    if isinstance(error, (json.JSONDecodeError, UnicodeError)) and stage == 'INPUT':
        return 'INVALID_JSON'
    return 'VALIDATION_FAILED'


def prepare_file(source, destination, *, now=None, clock=None):
    stage = 'INPUT'
    try:
        if now is not None and clock is not None:
            raise PreparationError('AMBIGUOUS_CLOCK')
        clock = clock or ((lambda: now) if now is not None else lambda: datetime.now(timezone.utc))
        previous = None

        def current_time():
            nonlocal previous
            value = clock()
            if value.tzinfo is None or (previous is not None and value < previous):
                raise PreparationError('CLOCK_CHANGED')
            previous = value
            return value

        source, destination = Path(source), Path(destination)
        if (source.resolve() == destination.resolve() or
                (source.exists() and destination.exists() and source.samefile(destination))):
            raise PreparationError('PATH_ALIAS')
        with source.open('rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise PreparationError('INPUT_TOO_LARGE')
        value = json.loads(raw)
        for stage, execute in [('SOURCE_VALIDATION', build_research),
                               ('HANDOFF', compile_handoff),
                               ('CONSISTENCY_REVIEW', review),
                               ('MODEL_REQUESTS', build_adapter_requests)]:
            value = execute(value, now=current_time())
        stage = 'PREFLIGHT'
        preflight(value, dry_run=True, now=current_time())
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8')) > 65536:
            raise PreparationError('OUTPUT_TOO_LARGE')
        stage = 'PUBLICATION'
        # Revalidate freshness immediately before the atomic write.
        preflight(value, dry_run=True, now=current_time())
        publish_report(value, destination)
    except (ValueError, OSError, TypeError, KeyError) as error:
        code = preparation_error_code(error, stage)
        return {'status': 'BLOCKED', 'stage': stage, 'error_code': code,
                'guidance': ERROR_GUIDANCE[code],
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
