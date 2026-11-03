"""Render bounded, allowlisted execution status into a GitHub job summary."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from ai_meeting_runtime import ANALYSTS, SAFE_ERROR_CODES, valid_execution_id
from agent_research_runtime_v233 import utc_time

STAGES = {'INPUT', 'CONFIGURATION', 'INFERENCE', 'PUBLICATION', 'COMPLETED'}
CODES = SAFE_ERROR_CODES | {'FILE_ERROR', 'INPUT_OR_VALIDATION_ERROR'}
FIELDS = {'version', 'status', 'stage', 'agent', 'phase', 'attempted_calls',
          'validated_responses', 'error_code', 'execution_id', 'started_at_utc', 'updated_at_utc'}
HINTS = {
    'OPENAI_API_KEY_REQUIRED': 'GitHub Actions의 OPENAI_API_KEY secret 설정을 확인하세요.',
    'MODEL_REQUIRED': '지원되는 모델 이름을 지정하세요.',
    'LIVE_PROVIDER_NOT_ENABLED': '명시적인 유료 호출 승인이 필요합니다.',
    'PROVIDER_AUTHENTICATION_FAILED': 'API 키가 유효한지 확인하세요. 원본 응답은 공개하지 않습니다.',
    'PROVIDER_ACCESS_DENIED': '프로젝트·계정·모델 접근 권한을 확인하세요.',
    'PROVIDER_MODEL_OR_ENDPOINT_NOT_FOUND': '모델 이름과 해당 모델의 API 접근 가능 여부를 확인하세요.',
    'PROVIDER_REQUEST_REJECTED': '선택한 모델의 Chat Completions·JSON schema·요청 옵션 지원 여부를 확인하세요.',
    'PROVIDER_RATE_OR_QUOTA_LIMIT': '호출 제한 또는 사용량·결제 한도를 확인하세요. 자동 재시도하지 않습니다.',
    'PROVIDER_UPSTREAM_ERROR': '제공자 서버 오류입니다. 자동 재시도하지 않습니다.',
    'PROVIDER_TIMEOUT': '요청 시간이 초과됐습니다. 호출 시도는 과금 여부를 확정하지 않습니다.',
    'PROVIDER_OUTPUT_TRUNCATED': '출력이 잘려 완료된 회의로 게시하지 않았습니다.',
    'PROVIDER_REFUSED': '모델이 응답을 거절해 회의를 완료하지 않았습니다.',
    'INPUT_OR_VALIDATION_ERROR': '원본 데이터의 최신성·형식과 이전 준비 단계 로그를 확인하세요.',
    'FILE_ERROR': '입력·출력 파일과 실행 환경의 접근 권한을 확인하세요.',
}


def validate_progress_state(value):
    attempted, validated = value['attempted_calls'], value['validated_responses']
    # Calls are sequential: at most one attempted response can remain unvalidated.
    if attempted-validated > 1:
        raise ValueError('IMPOSSIBLE_SEQUENTIAL_PROGRESS')
    plan = ([(agent, 'ANALYSIS') for agent in ANALYSTS] +
            [(agent, 'PEER_REVIEW') for agent in ANALYSTS] + [('COMMANDER', 'CONCLUSION')])
    expected = (None, None) if attempted == 0 else plan[attempted-1]
    if (value['agent'], value['phase']) != expected:
        raise ValueError('ROLE_PHASE_DO_NOT_MATCH_CALL_COUNT')
    if value['stage'] in ('INPUT', 'CONFIGURATION') and attempted != 0:
        raise ValueError('CALLS_BEFORE_INFERENCE')
    if value['stage'] in ('PUBLICATION', 'COMPLETED') and (attempted, validated) != (7, 7):
        raise ValueError('PUBLICATION_BEFORE_COMPLETE_RESPONSES')
    if (value['stage'] == 'COMPLETED') != (value['status'] == 'COMPLETED'):
        raise ValueError('INCONSISTENT_COMPLETION_STAGE')


def render_status(value, *, expected_execution_id=None, now=None):
    if not isinstance(value, dict) or set(value) != FIELDS or value['version'] != 'MEETING_DIAGNOSTICS_2':
        raise ValueError('INVALID_DIAGNOSTICS')
    if not valid_execution_id(value['execution_id']):
        raise ValueError('INVALID_EXECUTION_ID')
    if expected_execution_id is not None and (
            not valid_execution_id(expected_execution_id) or value['execution_id'] != expected_execution_id):
        raise ValueError('DIAGNOSTICS_FROM_DIFFERENT_EXECUTION')
    now = now or datetime.now(timezone.utc)
    started, updated = utc_time(value['started_at_utc']), utc_time(value['updated_at_utc'])
    if not started <= updated <= now or not 0 <= (now-updated).total_seconds() <= 8*3600:
        raise ValueError('STALE_OR_INVALID_DIAGNOSTIC_TIME')
    if value['status'] not in ('RUNNING', 'FAILED', 'COMPLETED') or value['stage'] not in STAGES:
        raise ValueError('INVALID_DIAGNOSTIC_STATE')
    if value['agent'] not in (*ANALYSTS, 'COMMANDER', None) or value['phase'] not in ('ANALYSIS', 'PEER_REVIEW', 'CONCLUSION', None):
        raise ValueError('INVALID_DIAGNOSTIC_ROLE')
    attempted, validated = value['attempted_calls'], value['validated_responses']
    if type(attempted) is not int or type(validated) is not int or not 0 <= validated <= attempted <= 7:
        raise ValueError('INVALID_DIAGNOSTIC_COUNTS')
    code = value['error_code']
    if code is not None and (not isinstance(code, str) or code not in CODES):
        raise ValueError('UNTRUSTED_ERROR_CODE')
    if (value['status'] == 'FAILED') != (code is not None):
        raise ValueError('INCONSISTENT_ERROR_STATUS')
    validate_progress_state(value)
    lines = ['## AI 회의 실행 진단', '',
             '- 기록 실행 ID: '+value['execution_id'], '- 마지막 기록 시각: '+updated.isoformat(),
             '- 상태: '+value['status'], '- 실행 단계: '+value['stage'],
             '- 마지막 관측 역할/단계: '+(value['agent'] or '없음')+' / '+(value['phase'] or '없음'),
             '- 호출 시도: '+str(attempted)+'/7', '- 검증된 응답: '+str(validated)+'/7']
    if code:
        lines += ['- 오류 코드: '+code, '', HINTS.get(code, '관련 단계 로그와 입력·응답 형식을 확인하세요.')]
    if value['status'] == 'COMPLETED':
        lines += ['', '회의 파일 생성 완료입니다. 최종 공개 검증·Pages 배포 성공은 이후 단계에서 별도로 확인하세요.']
    else:
        lines += ['', '이번 실행의 회의 완료나 공개 게시 성공을 의미하지 않습니다.']
    lines += ['', '호출 시도 수는 결제 금액이나 실제 과금 횟수가 아닙니다. 주문 실행 없음.', '']
    return '\n'.join(lines)


def read_summary(path, *, expected_execution_id=None, now=None):
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(8193)
        if len(raw) > 8192:
            raise ValueError('DIAGNOSTICS_TOO_LARGE')
        return render_status(json.loads(raw), expected_execution_id=expected_execution_id, now=now)
    except (ValueError, TypeError, KeyError, OSError):
        return ('## AI 회의 실행 진단\n\n유효한 실행 진단 없음. 설정 검사·데이터 준비·작업 취소 로그를 확인하세요. '
                '실제 호출이나 게시 성공 여부를 이 요약만으로 판단할 수 없습니다.\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('diagnostics')
    parser.add_argument('summary')
    parser.add_argument('--expected-execution-id', help='Reject a status from any other workflow run or attempt')
    args = parser.parse_args()
    source, target = Path(args.diagnostics), Path(args.summary)
    if source.resolve() == target.resolve() or (source.exists() and target.exists() and source.samefile(target)):
        parser.exit(1, 'Diagnostic input and summary output must differ.\n')
    with target.open('a', encoding='utf-8') as stream:
        stream.write('\n'+read_summary(source, expected_execution_id=args.expected_execution_id))


if __name__ == '__main__':
    main()
