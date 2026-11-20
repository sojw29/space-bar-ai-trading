"""Inspect/compare exported meeting archives locally. No network or file writes."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from html import escape
from pathlib import Path
import re
import sys

from ai_meeting_runtime import meeting_input_refs

VERDICTS = ('OBSERVATION_ONLY', 'REVIEW_NEEDED', 'INSUFFICIENT_DATA')
PLAN = [(agent, phase) for phase in ('ANALYSIS', 'PEER_REVIEW')
        for agent in ('ATLAS', 'QUANT', 'GUARDIAN')] + [('COMMANDER', 'CONCLUSION')]
WRAPPER = {'version', 'archived_at_utc', 'research_only', 'orders_enabled',
           'trade_authorization', 'process_liveness_verified', 'record'}
RECORD = {'execution_mode', 'model_inference_performed', 'workflow_execution_id',
          'market_source', 'model', 'source_generated_at_utc', 'started_at_utc',
          'generated_at_utc', 'final_verdict', 'verdict_counts', 'transcript'}
STATEMENT = {'id', 'agent', 'phase', 'verdict', 'summary', 'concerns'}
MAX_BYTES = 262144


def require(condition):
    if not condition:
        raise ValueError('INVALID_MEETING_ARCHIVE')


def timestamp(value):
    require(isinstance(value, str))
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0)
    return parsed


def validate_archive(value, *, now=None):
    require(isinstance(value, dict) and set(value) == WRAPPER)
    require(value['version'] == 'SPACEBAR_MEETING_ARCHIVE_1'
            and value['research_only'] is True and value['orders_enabled'] is False
            and value['trade_authorization'] == 'DENIED'
            and value['process_liveness_verified'] is False)
    record = value['record']
    require(isinstance(record, dict) and set(record) - {"input_statement_ids"} == RECORD)
    require(record['execution_mode'] in ('OFFLINE_FIXTURE', 'LIVE_PROVIDER'))
    require(record['model_inference_performed'] is (record['execution_mode'] == 'LIVE_PROVIDER'))
    identity = record['workflow_execution_id']
    require(identity is None or (isinstance(identity, str) and re.fullmatch('[a-f0-9]{32}', identity)))
    require(record['market_source'] in (None, 'BYBIT_USDT_PERPETUAL_5M', 'OKX_USDT_PERPETUAL_5M'))
    require(isinstance(record['model'], str) and record['model'].strip() and len(record['model']) <= 120)
    source, started, finished = (timestamp(record[key]) for key in
                                ('source_generated_at_utc', 'started_at_utc', 'generated_at_utc'))
    archived = timestamp(value['archived_at_utc'])
    require(source <= started <= finished <= archived <= (now or datetime.now(timezone.utc)))
    require(record['final_verdict'] in VERDICTS)
    statements = record['transcript']
    require(isinstance(statements, list) and len(statements) == 7)
    counts = Counter()
    for i, (statement, (agent, phase)) in enumerate(zip(statements, PLAN), 1):
        require(isinstance(statement, dict) and set(statement) == STATEMENT)
        require((statement['id'], statement['agent'], statement['phase']) == (f'M{i:02}', agent, phase))
        require(statement['verdict'] in VERDICTS)
        require(isinstance(statement['summary'], str) and statement['summary'].strip()
                and len(statement['summary']) <= 1600)
        concerns = statement['concerns']
        require(isinstance(concerns, list) and len(concerns) <= 8
                and all(isinstance(c, str) and c.strip() and len(c) <= 400 for c in concerns))
        counts[statement['verdict']] += 1
    if 'input_statement_ids' in record:
        inputs = record['input_statement_ids']
        require(isinstance(inputs, list) and len(inputs) == len(PLAN))
        legacy = inputs[-1] == []
        require(inputs == [meeting_input_refs(i, legacy=legacy) for i in range(len(PLAN))])
    saved_counts = record['verdict_counts']
    require(isinstance(saved_counts, dict) and set(saved_counts) == set(VERDICTS)
            and all(type(saved_counts[key]) is int and saved_counts[key] == counts[key] for key in VERDICTS))
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def read_archive(path, *, now=None):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES)
    return validate_archive(json.loads(raw, object_pairs_hook=unique_object), now=now)


def describe(value):
    record = value['record']
    return {key: record[key] for key in ('workflow_execution_id', 'execution_mode',
            'model_inference_performed', 'market_source', 'model', 'generated_at_utc',
            'final_verdict', 'verdict_counts')}


def compare_archives(left, right, *, now=None):
    validate_archive(left, now=now)
    validate_archive(right, now=now)
    a, b = left['record'], right['record']
    market = ('UNKNOWN' if a['market_source'] is None or b['market_source'] is None else
              'SAME' if a['market_source'] == b['market_source'] else 'DIFFERENT')
    def relation(key):
        delta = (timestamp(b[key])-timestamp(a[key])).total_seconds()
        return {'order': 'RIGHT_LATER' if delta > 0 else 'RIGHT_EARLIER' if delta < 0 else 'SAME_TIME',
                'right_minus_left_seconds': delta}
    statements = [{'id': x['id'], 'agent': x['agent'], 'phase': x['phase'],
                   'left_verdict': x['verdict'], 'right_verdict': y['verdict'],
                   'verdict_changed': x['verdict'] != y['verdict'],
                   'summary_changed': x['summary'] != y['summary'],
                   'concerns_changed': x['concerns'] != y['concerns']}
                  for x, y in zip(a['transcript'], b['transcript'])]
    change_keys = ('verdict_changed', 'summary_changed', 'concerns_changed')
    changed_ids = [s['id'] for s in statements if any(s[key] for key in change_keys)]
    transitions = []
    for old in VERDICTS:
        for new in VERDICTS:
            ids = [s['id'] for s in statements if (s['left_verdict'], s['right_verdict']) == (old, new)]
            transitions.append({'left_verdict': old, 'right_verdict': new,
                                'count': len(ids), 'statement_ids': ids})
    context = []
    if market == 'UNKNOWN':
        context.append('MARKET_SOURCE_UNKNOWN')
    elif market == 'DIFFERENT':
        context.append('MARKET_SOURCE_CHANGED')
    if a['model'] != b['model']:
        context.append('MODEL_CHANGED')
    if a['execution_mode'] != b['execution_mode']:
        context.append('EXECUTION_MODE_CHANGED')
    if relation('source_generated_at_utc')['order'] != 'SAME_TIME':
        context.append('SOURCE_TIME_CHANGED')
    if relation('generated_at_utc')['order'] == 'RIGHT_EARLIER':
        context.append('RIGHT_COMPLETION_EARLIER')
    return {'version': 'MEETING_ARCHIVE_COMPARISON_1', 'research_only': True,
            'orders_enabled': False, 'left': describe(left), 'right': describe(right),
            'market_comparison': market,
            'comparison_context': context,
            'time_relation': {'basis': 'RECORDED_UTC_TIMESTAMPS',
                              'source': relation('source_generated_at_utc'),
                              'completion': relation('generated_at_utc')},
            'model_changed': a['model'] != b['model'],
            'execution_mode_changed': a['execution_mode'] != b['execution_mode'],
            'final_verdict_changed': a['final_verdict'] != b['final_verdict'],
            'verdict_transitions': transitions,
            'verdict_count_delta': {key: b['verdict_counts'][key]-a['verdict_counts'][key] for key in VERDICTS},
            'change_summary': {'changed_statement_count': len(changed_ids),
                               'changed_statement_ids': changed_ids,
                               **{key: sum(s[key] for s in statements) for key in change_keys}},
            'statements': statements}


def render_report(left, right=None, *, now=None):
    validate_archive(left, now=now)
    comparison = compare_archives(left, right, now=now) if right is not None else None
    records = [left['record']] + ([right['record']] if right is not None else [])
    def cell(value):
        return escape('미기록' if value is None else str(value))
    def table(headers, rows, *, changed_rows=(), label=None):
        region = (' role="region" tabindex="0" aria-label="'+cell(label)+'"') if label else ''
        return '<div class="table"'+region+'><table><thead><tr>'+''.join('<th scope="col">'+cell(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join(
            ('<tr class="changed-row">' if index in changed_rows else '<tr>')+''.join('<td>'+cell(x)+'</td>' for x in row)+'</tr>' for index, row in enumerate(rows))+'</tbody></table></div>'
    verdict_labels = {'OBSERVATION_ONLY': '관측 요약', 'REVIEW_NEEDED': '추가 검토 필요', 'INSUFFICIENT_DATA': '자료 부족'}
    phase_labels = {'ANALYSIS': '초기 분석', 'PEER_REVIEW': '상호 검토', 'CONCLUSION': '최종 결론'}
    mode_labels = {'OFFLINE_FIXTURE': '오프라인 테스트 (OFFLINE_FIXTURE)', 'LIVE_PROVIDER': '모델 API 실행 기록 (LIVE_PROVIDER)'}
    market_labels = {None: '미기록', 'BYBIT_USDT_PERPETUAL_5M': 'Bybit USDT 무기한 5분봉', 'OKX_USDT_PERPETUAL_5M': 'OKX USDT 무기한 5분봉'}
    def metadata(record, key):
        value = record[key]
        if key in ('source_generated_at_utc', 'generated_at_utc'):
            try:
                local = timestamp(value).astimezone(timezone(timedelta(hours=9))).isoformat(sep=' ')
            except OverflowError:
                local = '변환 범위 초과'
            return value+' (UTC) / '+local+' (KST)'
        mapping = {'execution_mode': mode_labels, 'market_source': market_labels, 'final_verdict': verdict_labels}.get(key)
        return mapping[value] if mapping is not None else value
    fields = [('실행 ID', 'workflow_execution_id'), ('실행 모드', 'execution_mode'),
              ('데이터 출처', 'market_source'), ('모델', 'model'),
              ('원본 생성 UTC / KST', 'source_generated_at_utc'), ('회의 완료 UTC / KST', 'generated_at_utc'),
              ('최종 상태', 'final_verdict')]
    rows = [[label, *[metadata(r, key) for r in records]] for label, key in fields]
    rows.extend([[verdict_labels[verdict]+' 발언 수', *[r['verdict_counts'][verdict] for r in records]] for verdict in VERDICTS])
    body = '<h2 id="record-metadata">기록 정보</h2>'+table(['항목', '왼쪽 기록', '오른쪽 기록'] if comparison else ['항목', '저장 기록'], rows)
    if comparison:
        context_labels = {'MARKET_SOURCE_UNKNOWN': '시장 출처 미기록으로 출처 동일 여부 미확인',
                          'MARKET_SOURCE_CHANGED': '시장 출처가 다름', 'MODEL_CHANGED': '모델이 다름',
                          'EXECUTION_MODE_CHANGED': '실행 모드가 다름 (테스트/API 실행 표시 구분)',
                          'SOURCE_TIME_CHANGED': '원본 데이터 생성 시각이 다름',
                          'RIGHT_COMPLETION_EARLIER': '오른쪽 기록의 회의 완료 시각이 더 이름'}
        context_items = comparison['comparison_context']
        context_html = ('<ul>'+''.join('<li>'+cell(context_labels[key])+'</li>' for key in context_items)+'</ul>'
                        if context_items else '<p>표시된 비교 조건 차이 없음 · 입력 데이터 동일성이나 실제 실행을 확인한 결과는 아닙니다.</p>')
        body = '<section aria-label="비교 조건 요약"><h2 id="comparison-context">비교 조건 요약</h2>'+context_html+'<p>기록된 조건 차이의 안내이며 비교 가능성·정확도·수익성 점수가 아닙니다.</p></section>'+body
        transitions = comparison['verdict_transitions']
        body += '<h2 id="verdict-transitions">판단 전환표</h2><p>행은 왼쪽 기록의 판단, 열은 오른쪽 기록의 판단입니다. 같은 판단을 유지한 발언도 포함하며 총 7개입니다. 전환이나 건수 감소가 정확도·수익성 향상을 뜻하지 않습니다.</p>'+table(
            ['왼쪽 → 오른쪽', *[verdict_labels[key] for key in VERDICTS]],
            [[verdict_labels[old], *[next(t['count'] for t in transitions if t['left_verdict'] == old and t['right_verdict'] == new) for new in VERDICTS]] for old in VERDICTS])
        body += table(['검토 상태', '발언 수 증감 (오른쪽 − 왼쪽)'],
                      [[verdict_labels[key], comparison['verdict_count_delta'][key]] for key in VERDICTS])
        switched = [t for t in transitions if t['count'] and t['left_verdict'] != t['right_verdict']]
        if switched:
            body += table(['판단 전환', '건수', '발언 ID'],
                          [[verdict_labels[t['left_verdict']]+' → '+verdict_labels[t['right_verdict']], t['count'], ', '.join(t['statement_ids'])] for t in switched])
        else:
            body += '<p>판단 전환 없음 · 요약이나 우려 내용의 변경 여부는 별도 표에서 확인하세요.</p>'
        summary = comparison['change_summary']
        body += '<h2 id="changed-statements">변경된 발언 요약</h2>'+table(['항목', '건수'], [
            ['변경된 발언 (전체 7개)', summary['changed_statement_count']],
            ['판단 변경', summary['verdict_changed']], ['요약 변경', summary['summary_changed']],
            ['우려 변경', summary['concerns_changed']]])
        body += '<p>변경 발언 수는 중복 없이 집계합니다. 유형별 건수는 한 발언이 여러 유형에 포함될 수 있습니다. 모델·출처·시간 변경은 발언 변경 건수와 별도로 표시됩니다.</p>'
        changed = [s for s in comparison['statements'] if s['id'] in summary['changed_statement_ids']]
        if changed:
            body += table(['변경 ID', '역할', '단계', '변경 항목'], [
                [s['id'], s['agent'], phase_labels[s['phase']], ' · '.join(label for key, label in
                 [('verdict_changed', '판단'), ('summary_changed', '요약'), ('concerns_changed', '우려')] if s[key])]
                for s in changed])
        else:
            body += '<p>변경된 발언 없음 · 메타데이터와 최종 상태 비교는 아래에 별도로 표시됩니다.</p>'
        order_labels = {'RIGHT_LATER': '오른쪽 기록이 나중', 'RIGHT_EARLIER': '오른쪽 기록이 먼저', 'SAME_TIME': '동일 시각'}
        body += '<h2 id="record-times">기록 시각 관계</h2><p>입력 순서를 유지하며 자동으로 재정렬하지 않습니다. 시간 차이는 오른쪽 − 왼쪽(초)입니다. 원본 데이터 시각과 회의 완료 시각을 따로 비교합니다.</p>'+table(
            ['비교 기준', '선후 관계', '오른쪽 − 왼쪽(초)'],
            [[label, order_labels[comparison['time_relation'][key]['order']],
              comparison['time_relation'][key]['right_minus_left_seconds']]
             for label, key in [('원본 데이터 생성', 'source'), ('회의 완료', 'completion')]])
        body += '<h2 id="metadata-changes">변경 요약</h2>'+table(['항목', '결과'], [
            ['시장 출처 비교', {'SAME': '같은 시장 출처', 'DIFFERENT': '다른 시장 출처', 'UNKNOWN': '시장 출처 미확인 (UNKNOWN)'}[comparison['market_comparison']]],
            ['모델 변경', '변경' if comparison['model_changed'] else '동일'],
            ['실행 모드 변경', '변경' if comparison['execution_mode_changed'] else '동일'],
            ['최종 상태 변경', '변경' if comparison['final_verdict_changed'] else '동일']])
        body += '<h2 id="statement-changes">발언별 변경 여부</h2><p>변경된 발언은 ‘변경 있음’ 표시와 굵은 테두리로 구분합니다. 모든 발언을 원래 순서로 표시합니다. 표를 좌우로 스크롤하면 나머지 열을 볼 수 있습니다.</p>'+table(
            ['ID', '변경 상태', '역할', '단계', '왼쪽 판단', '오른쪽 판단', '판단', '요약', '우려'],
            [[s['id'], '변경 있음' if s['id'] in summary['changed_statement_ids'] else '변경 없음', s['agent'], phase_labels[s['phase']], verdict_labels[s['left_verdict']], verdict_labels[s['right_verdict']],
              *['변경' if s[k] else '동일' for k in ('verdict_changed', 'summary_changed', 'concerns_changed')]]
             for s in comparison['statements']],
            changed_rows={i for i, s in enumerate(comparison['statements']) if s['id'] in summary['changed_statement_ids']},
            label='발언별 변경 여부 표 · 좌우 스크롤 가능')
    sections = [('record-metadata', '기록 정보')]
    if comparison:
        sections = [('comparison-context', '비교 조건 요약'), *sections,
                    ('verdict-transitions', '판단 전환표'), ('changed-statements', '변경된 발언 요약'),
                    ('record-times', '기록 시각 관계'), ('metadata-changes', '변경 요약'),
                    ('statement-changes', '발언별 변경 여부')]
    if any('input_statement_ids' in record for record in records):
        sections.append(('statement-inputs', '검토에 제공된 발언'))
        rows = []
        for side, record in zip(('왼쪽', '오른쪽'), records):
            inputs = record.get('input_statement_ids')
            if inputs is None:
                rows.append([side if comparison else '저장 기록', '미기록', '미기록'])
                continue
            statements = {item['id']: item for item in record['transcript']}
            for item, refs in zip(record['transcript'][3:], inputs[3:]):
                rows.append([side if comparison else '저장 기록',
                             item['id']+' '+item['agent'],
                             ' · '.join(ref+' '+statements[ref]['agent'] for ref in refs) or '미기록'])
        body += '<h2 id="statement-inputs">검토에 제공된 발언</h2>'+table(
            ['기록', '검토 또는 결론', '제공된 발언 ID와 역할'], rows)
    navigation = '<nav aria-label="보고서 목차"><p>바로 이동</p><ul>'+''.join(
        '<li><a href="#'+key+'">'+label+'</a></li>' for key, label in sections)+'</ul></nav>'
    body = body.replace('</h2>', '</h2><p class="back-top"><a href="#report-top">목차로 돌아가기</a></p>')
    return ('<!doctype html><html lang="ko"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>SPACE BAR 저장 회의 보고서</title><style>body{font:16px system-ui;max-width:1100px;margin:24px auto;padding:16px;color:#172b40}table{border-collapse:collapse;width:100%}th,td{border:1px solid #a9b9c9;padding:10px;text-align:left;overflow-wrap:anywhere}.table{overflow-x:auto}p{line-height:1.6}nav{padding:12px;border:1px solid #a9b9c9}nav ul{display:flex;flex-wrap:wrap;gap:12px 24px;padding-left:20px}a{color:#075b9c}a:focus-visible{outline:3px solid #075b9c;outline-offset:3px}h2{scroll-margin-top:16px}.back-top{font-size:14px}.changed-row{background:#edf5ff}.changed-row td:first-child{border-left:4px solid #172b40;font-weight:700}.table[role=region] table{min-width:880px}.table:focus-visible{outline:3px solid #075b9c;outline-offset:3px}'
            '@page{size:A4 landscape;margin:12mm}@media print{.table[role=region] table{min-width:0}nav,.back-top{display:none}body{max-width:none;margin:0;padding:0;font-size:10pt;color:#000}.table{overflow:visible}table{table-layout:fixed}th,td{padding:5px}thead{display:table-header-group}tr{break-inside:avoid;page-break-inside:avoid}h1,h2{break-after:avoid}section{break-inside:avoid}p{line-height:1.4}}</style>'
            '<h1 id="report-top">SPACE BAR · 저장 회의 보고서</h1>'
            '<p>과거 보관 기록의 형식 검사 결과입니다. 실제 모델 실행의 진위·현재 프로세스 생존·거래 승인을 확인하지 않습니다. '
            'OFFLINE_FIXTURE는 테스트 기록, LIVE_PROVIDER는 저장된 API 실행 표시입니다.</p>'
            '<p>KST는 UTC+09:00 한국시간입니다. 원본 UTC와 같은 순간을 표시하며 입력 기록과 시간 차이 계산은 변경하지 않습니다.</p>'
            '<p>왼쪽·오른쪽은 입력 순서입니다. 변경은 정확도·수익성 향상을 뜻하지 않습니다. UNKNOWN은 시장 출처 미확인입니다.</p>'
            +navigation+body+'</html>')


def main():
    parser = argparse.ArgumentParser(description='Inspect one saved meeting archive or compare two; offline/read-only')
    parser.add_argument('left')
    parser.add_argument('right', nargs='?')
    parser.add_argument('--format', choices=('json', 'html'), default='json')
    args = parser.parse_args()
    try:
        left = read_archive(args.left)
        right = read_archive(args.right) if args.right else None
        result = compare_archives(left, right) if right is not None else {
            'version': 'MEETING_ARCHIVE_INSPECTION_1', 'research_only': True,
            'orders_enabled': False, 'record': describe(left)}
        output = render_report(left, right) if args.format == 'html' else json.dumps(result, ensure_ascii=False, indent=2)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, OverflowError):
        print('Meeting archive unavailable or invalid; no files were changed.', file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
