"""Inspect/compare exported meeting archives locally. No network or file writes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

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
    require(isinstance(record, dict) and set(record) == RECORD)
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
    return {'version': 'MEETING_ARCHIVE_COMPARISON_1', 'research_only': True,
            'orders_enabled': False, 'left': describe(left), 'right': describe(right),
            'market_comparison': market,
            'execution_mode_changed': a['execution_mode'] != b['execution_mode'],
            'final_verdict_changed': a['final_verdict'] != b['final_verdict'],
            'statements': [{'id': x['id'], 'agent': x['agent'], 'phase': x['phase'],
                'left_verdict': x['verdict'], 'right_verdict': y['verdict'],
                'verdict_changed': x['verdict'] != y['verdict'],
                'summary_changed': x['summary'] != y['summary'],
                'concerns_changed': x['concerns'] != y['concerns']}
                for x, y in zip(a['transcript'], b['transcript'])]}


def main():
    parser = argparse.ArgumentParser(description='Inspect one saved meeting archive or compare two; offline/read-only')
    parser.add_argument('left')
    parser.add_argument('right', nargs='?')
    args = parser.parse_args()
    try:
        left = read_archive(args.left)
        result = compare_archives(left, read_archive(args.right)) if args.right else {
            'version': 'MEETING_ARCHIVE_INSPECTION_1', 'research_only': True,
            'orders_enabled': False, 'record': describe(left)}
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, OverflowError):
        print('Meeting archive unavailable or invalid; no files were changed.', file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
