"""Validate completed live research transcripts before public Pages publication.

Carry-over trusts only the existing fixed Pages origin, not arbitrary URLs.
No API keys or model calls are used here; fixture transcripts are never published.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import build_opener

from agent_research_runtime_v233 import utc_time
from ai_meeting_runtime import (ANALYSTS, VERDICTS, MeetingError, NoRedirect,
                                publish_report, validate_statement)
from provider_transport_preflight_v240 import preflight
from market_source_provenance import with_market_source

PUBLIC_URL = 'https://sojw29.github.io/space-bar-ai-trading/ai_meeting.json'
MAX_BYTES = 262144
FIELDS = {'version', 'status', 'execution_mode', 'model_inference_performed',
          'ai_agents_running', 'research_only', 'orders_enabled', 'trade_authorization',
          'source_generated_at_utc', 'started_at_utc', 'generated_at_utc',
          'request_sha256', 'model', 'call_count', 'final_verdict', 'transcript'}


def validate_public_report(report, *, bundle=None, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise MeetingError('NAIVE_NOW')
    allowed = (FIELDS, FIELDS | {'market_source'}, FIELDS | {'statement_refs'},
               FIELDS | {'market_source', 'statement_refs'})
    if not isinstance(report, dict) or set(report) not in allowed:
        raise MeetingError('INVALID_REPORT_FIELDS')
    with_market_source(report, {})
    for key, expected in {'version': 'AI_MEETING_1', 'status': 'COMPLETED',
                          'execution_mode': 'LIVE_PROVIDER', 'model_inference_performed': True,
                          'ai_agents_running': False, 'research_only': True, 'orders_enabled': False,
                          'trade_authorization': 'DENIED'}.items():
        if type(report[key]) is not type(expected) or report[key] != expected:
            raise MeetingError('NOT_A_COMPLETED_LIVE_RESEARCH_MEETING')
    source, started, finished = [utc_time(report[k]) for k in
                                 ('source_generated_at_utc', 'started_at_utc', 'generated_at_utc')]
    if not source <= started <= finished <= now or not 0 <= (now-source).total_seconds() <= 8*3600:
        raise MeetingError('STALE_OR_INVALID_TIMESTAMPS')
    if not isinstance(report['request_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', report['request_sha256']):
        raise MeetingError('INVALID_REQUEST_HASH')
    if not isinstance(report['model'], str) or not 1 <= len(report['model'].strip()) <= 120:
        raise MeetingError('INVALID_MODEL')
    if type(report['call_count']) is not int or report['call_count'] != 7:
        raise MeetingError('INVALID_CALL_COUNT')
    transcript = report['transcript']
    if not isinstance(transcript, list) or len(transcript) != 7:
        raise MeetingError('INCOMPLETE_TRANSCRIPT')
    for index, (agent, item) in enumerate(zip((*ANALYSTS, *ANALYSTS, 'COMMANDER'), transcript)):
        phase = 'ANALYSIS' if index < 3 else 'PEER_REVIEW' if index < 6 else 'CONCLUSION'
        if (not isinstance(item, dict) or set(item) != {'agent', 'phase', 'summary', 'concerns', 'verdict'}
                or item['agent'] != agent or item['phase'] != phase):
            raise MeetingError('INVALID_TRANSCRIPT_ORDER')
        validate_statement({k: item[k] for k in ('summary', 'concerns', 'verdict')})
    refs = report.get('statement_refs')
    if refs is not None:
        if not isinstance(refs, list) or len(refs) != 7:
            raise MeetingError('INVALID_STATEMENT_REFS')
        for index, (agent, entry) in enumerate(zip((*ANALYSTS, *ANALYSTS, 'COMMANDER'), refs)):
            phase = 'ANALYSIS' if index < 3 else 'PEER_REVIEW' if index < 6 else 'CONCLUSION'
            expected_refs = ['M%02d' % (index-2)] if 3 <= index <= 5 else []
            if (not isinstance(entry, dict) or
                    set(entry) != {'id', 'agent', 'phase', 'references'} or
                    entry['id'] != 'M%02d' % (index+1) or
                    entry['agent'] != agent or entry['phase'] != phase or
                    entry['references'] != expected_refs):
                raise MeetingError('INVALID_STATEMENT_REF')
    final = transcript[-1]['verdict']
    if any(t['verdict'] == 'INSUFFICIENT_DATA' for t in transcript):
        final = 'INSUFFICIENT_DATA'
    elif any(t['agent'] == 'GUARDIAN' and t['verdict'] == 'REVIEW_NEEDED' for t in transcript):
        final = 'REVIEW_NEEDED'
    if report['final_verdict'] not in VERDICTS or report['final_verdict'] != final:
        raise MeetingError('FINAL_VERDICT_MISMATCH')
    if bundle is not None:
        envelope = preflight(bundle, dry_run=True, now=now)
        if (envelope['request_sha256'] != report['request_sha256'] or
                utc_time(envelope['source_generated_at_utc']) != source or
                bundle.get('market_source') != report.get('market_source')):
            raise MeetingError('REQUEST_PROVENANCE_MISMATCH')
    return deepcopy(report)


def restore_previous(destination, *, now=None):
    """Reuse only a still-valid snapshot; missing/stale/unavailable means no transcript."""
    destination = Path(destination)
    # Remove an existing candidate so invalid restore can never leave stale output.
    destination.unlink(missing_ok=True)
    try:
        with build_opener(NoRedirect()).open(PUBLIC_URL, timeout=10) as response:
            raw = response.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES:
            raise MeetingError('REPORT_TOO_LARGE')
        report = validate_public_report(json.loads(raw), now=now)
        publish_report(report, destination)
        return True
    except (ValueError, TypeError, KeyError, OSError, HTTPError, URLError):
        return False


def read_json(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES+1)
    if len(raw) > MAX_BYTES:
        raise MeetingError('INPUT_TOO_LARGE')
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description='Publish validated live research meeting snapshots')
    sub = parser.add_subparsers(dest='command', required=True)
    restore = sub.add_parser('restore')
    restore.add_argument('destination')
    publish = sub.add_parser('publish')
    publish.add_argument('source')
    publish.add_argument('destination')
    publish.add_argument('--bundle', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'restore':
            restored = restore_previous(args.destination)
            print('Previous live meeting retained.' if restored else 'No current live meeting to retain.')
        else:
            target = Path(args.destination)
            for name in (args.source, args.bundle):
                source = Path(name)
                if source.resolve() == target.resolve() or (source.exists() and target.exists() and source.samefile(target)):
                    raise MeetingError('INPUT_OUTPUT_ALIAS')
            report = validate_public_report(read_json(args.source), bundle=read_json(args.bundle))
            publish_report(report, target)
            print('Completed live research transcript validated for publication; no orders.')
    except (ValueError, TypeError, KeyError, OSError):
        parser.exit(1, 'Meeting publication failed validation.\n')


if __name__ == '__main__':
    main()
