"""Credential-free rehearsal of the same request-building chain used by live meetings.

No provider construction, model calls, publication, credentials or fixture inference.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from agent_research_runtime_v233 import build_research, utc_time
from agent_handoff_audit_v234 import compile_handoff
from research_consistency_review_v235 import review
from model_adapter_contract_v236 import build_adapter_requests
from provider_transport_preflight_v240 import preflight
from ai_meeting_runtime import publish_report

STAGES = ('SOURCE_VALIDATION', 'HANDOFF', 'CONSISTENCY_REVIEW', 'MODEL_REQUESTS', 'PREFLIGHT')
ERRORS = ('VALIDATION_FAILED', 'INPUT_UNAVAILABLE', 'INPUT_TOO_LARGE', 'INVALID_JSON')


def empty_report(now):
    return {'version': 'MEETING_READINESS_1', 'status': 'BLOCKED', 'stage': 'INPUT',
            'generated_at_utc': now.isoformat(), 'source_generated_at_utc': None,
            'checks': [], 'error_code': None, 'prepared_agent_count': 0,
            'planned_model_calls': 7, 'model_calls_performed': 0,
            'provider_verified': False, 'model_inference_performed': False,
            'research_only': True, 'orders_enabled': False}


def assess_readiness(brief, *, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('NAIVE_NOW')
    result = empty_report(now)
    current = brief
    steps = (build_research, compile_handoff, review, build_adapter_requests,
             lambda value, now: preflight(value, dry_run=True, now=now))
    for stage, execute in zip(STAGES, steps):
        result['stage'] = stage
        try:
            current = execute(current, now=now)
        except (ValueError, TypeError, KeyError):
            result['checks'].append({'stage': stage, 'status': 'FAIL'})
            result['error_code'] = 'VALIDATION_FAILED'
            return result
        result['checks'].append({'stage': stage, 'status': 'PASS'})
        if stage == 'SOURCE_VALIDATION':
            result['source_generated_at_utc'] = current['source_generated_at_utc']
    result.update(status='INPUTS_READY', prepared_agent_count=current['request_count'])
    return result


def check_file(source, *, now=None):
    now = now or datetime.now(timezone.utc)
    result = empty_report(now)
    try:
        with Path(source).open('rb') as stream:
            raw = stream.read(65537)
    except OSError:
        result['error_code'] = 'INPUT_UNAVAILABLE'
        return result
    if len(raw) > 65536:
        result['error_code'] = 'INPUT_TOO_LARGE'
        return result
    try:
        brief = json.loads(raw)
    except (ValueError, UnicodeError):
        result['error_code'] = 'INVALID_JSON'
        return result
    return assess_readiness(brief, now=now)


def render_summary(report, *, now=None):
    # Revalidate exact diagnostic state so arbitrary data never becomes Markdown.
    expected = set(empty_report(datetime.now(timezone.utc)))
    if not isinstance(report, dict) or set(report) != expected or report['version'] != 'MEETING_READINESS_1':
        raise ValueError('INVALID_READINESS_REPORT')
    now = now or datetime.now(timezone.utc)
    generated = utc_time(report['generated_at_utc'])
    if not 0 <= (now-generated).total_seconds() <= 8*3600:
        raise ValueError('STALE_READINESS_REPORT')
    for flag, value in {'provider_verified': False, 'model_inference_performed': False,
                        'research_only': True, 'orders_enabled': False}.items():
        if report[flag] is not value:
            raise ValueError('UNSAFE_READINESS_FLAGS')
    if type(report['model_calls_performed']) is not int or report['model_calls_performed'] != 0:
        raise ValueError('MODEL_CALLS_NOT_ZERO')
    if type(report['planned_model_calls']) is not int or report['planned_model_calls'] != 7:
        raise ValueError('INVALID_PLANNED_CALLS')
    checks = report['checks']
    if not isinstance(checks, list) or len(checks) > len(STAGES):
        raise ValueError('INVALID_CHECKS')
    for index, item in enumerate(checks):
        if (not isinstance(item, dict) or set(item) != {'stage', 'status'}
                or item['stage'] != STAGES[index] or item['status'] not in ('PASS', 'FAIL')):
            raise ValueError('INVALID_CHECK_SEQUENCE')
    ready = report['status'] == 'INPUTS_READY'
    if ready:
        source = utc_time(report['source_generated_at_utc'])
        if not source <= generated or not 0 <= (now-source).total_seconds() <= 8*3600:
            raise ValueError('STALE_READINESS_SOURCE')
        if (checks != [{'stage': stage, 'status': 'PASS'} for stage in STAGES]
                or report['stage'] != 'PREFLIGHT' or report['error_code'] is not None
                or type(report['prepared_agent_count']) is not int or report['prepared_agent_count'] != 4):
            raise ValueError('INCOMPLETE_READY_STATE')
    elif report['status'] == 'BLOCKED':
        if (report['error_code'] not in ERRORS or type(report['prepared_agent_count']) is not int or report['prepared_agent_count'] != 0
                or report['stage'] not in ('INPUT', *STAGES)):
            raise ValueError('INVALID_BLOCKED_STATE')
        if report['stage'] == 'INPUT':
            if checks or report['error_code'] == 'VALIDATION_FAILED':
                raise ValueError('INVALID_INPUT_FAILURE')
        elif (not checks or checks[-1] != {'stage': report['stage'], 'status': 'FAIL'}
              or any(c['status'] != 'PASS' for c in checks[:-1]) or report['error_code'] != 'VALIDATION_FAILED'):
            raise ValueError('INVALID_PIPELINE_FAILURE')
    else:
        raise ValueError('INVALID_STATUS')
    lines = ['## AI 회의 입력 준비 점검', '', '- 결과: '+report['status'],
             '- 점검 시각: '+generated.isoformat(),
             '- 마지막 점검 단계: '+report['stage'], '- 실제 모델 호출: 0회',
             '- 실제 모델 실행 시 예정 호출: 최대 7회', '']
    lines.extend('- '+item['stage']+': '+item['status'] for item in checks)
    if report['error_code']:
        lines += ['', '차단 코드: '+report['error_code']]
    lines += ['', 'INPUTS_READY는 데이터·요청 생성만 통과했다는 뜻입니다. API 키·모델 접근·과금·실제 추론은 검증하지 않았습니다.',
              '회의 실행·주문·트레이딩룸 게시 없음.', '']
    return '\n'.join(lines)


def summary_from_file(source):
    try:
        with Path(source).open('rb') as stream:
            raw = stream.read(16385)
        if len(raw) > 16384:
            raise ValueError('OVERSIZED_REPORT')
        return render_summary(json.loads(raw))
    except (ValueError, TypeError, KeyError, OSError):
        return ('## AI 회의 입력 준비 점검\n\n유효한 점검 기록 없음. 공개 데이터 수집 또는 이전 단계 로그를 확인하세요. '
                '입력 준비나 실제 AI 실행 성공을 의미하지 않습니다.\n')


def main():
    parser = argparse.ArgumentParser(description='Check model-meeting inputs without calling a provider')
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check')
    check.add_argument('source')
    check.add_argument('destination')
    summary = sub.add_parser('summary')
    summary.add_argument('source')
    summary.add_argument('destination')
    args = parser.parse_args()
    source, target = Path(args.source), Path(args.destination)
    if source.resolve() == target.resolve() or (source.exists() and target.exists() and source.samefile(target)):
        parser.exit(1, 'Readiness input and output must differ.\n')
    if args.command == 'summary':
        with target.open('a', encoding='utf-8') as stream:
            stream.write('\n'+summary_from_file(source))
    else:
        report = check_file(source)
        publish_report(report, target)
        print(render_summary(report))
        if report['status'] != 'INPUTS_READY':
            parser.exit(1)


if __name__ == '__main__':
    main()
