from copy import deepcopy
from datetime import datetime, timezone
import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ai_meeting_archive import compare_archives, read_archive, validate_archive, render_report, PLAN, MAX_BYTES

NOW = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)


def archive():
    return {'version': 'SPACEBAR_MEETING_ARCHIVE_1', 'archived_at_utc': '2026-11-14T12:00:00Z',
            'research_only': True, 'orders_enabled': False, 'trade_authorization': 'DENIED',
            'process_liveness_verified': False, 'record': {
                'execution_mode': 'OFFLINE_FIXTURE', 'model_inference_performed': False,
                'workflow_execution_id': None, 'market_source': None, 'model': 'fixture-model',
                'source_generated_at_utc': '2026-11-14T10:00:00Z',
                'started_at_utc': '2026-11-14T11:00:00Z', 'generated_at_utc': '2026-11-14T11:01:00Z',
                'final_verdict': 'OBSERVATION_ONLY',
                'verdict_counts': {'OBSERVATION_ONLY': 7, 'REVIEW_NEEDED': 0, 'INSUFFICIENT_DATA': 0},
                'transcript': [{'id': f'M{i:02}', 'agent': agent, 'phase': phase,
                    'verdict': 'OBSERVATION_ONLY', 'summary': 'private statement '+str(i),
                    'concerns': []} for i, (agent, phase) in enumerate(PLAN, 1)]}}


class MeetingArchiveTests(unittest.TestCase):
    def test_report_kst_rollover_preserves_utc_input_and_comparison(self):
        left, right = archive(), archive()
        for item in (left, right):
            item['record'].update(source_generated_at_utc='2026-11-14T16:30:00.123456Z',
                                  started_at_utc='2026-11-14T17:00:00Z',
                                  generated_at_utc='2026-11-14T17:01:00+00:00')
            item['archived_at_utc'] = '2026-11-14T18:00:00Z'
        original = deepcopy(left)
        before = compare_archives(left, right, now=NOW)
        for candidate in (None, right):
            report = render_report(left, candidate, now=NOW)
            self.assertIn('2026-11-14T16:30:00.123456Z (UTC)', report)
            self.assertIn('2026-11-15 01:30:00.123456+09:00 (KST)', report)
            self.assertIn('2026-11-15 02:01:00+09:00 (KST)', report)
        self.assertEqual(left, original)
        self.assertEqual(compare_archives(left, right, now=NOW), before)


    def test_report_emphasizes_all_change_types_without_hiding_unchanged_rows(self):
        class Rows(HTMLParser):
            def __init__(self):
                super().__init__()
                self.marked, self.current, self.in_cell = [], None, False
            def handle_starttag(self, tag, attrs):
                if tag == 'tr' and dict(attrs).get('class') == 'changed-row':
                    self.current = []
                if tag == 'td':
                    self.in_cell = True
            def handle_data(self, data):
                if self.current is not None and self.in_cell:
                    self.current.append(data)
            def handle_endtag(self, tag):
                if tag == 'td':
                    self.in_cell = False
                if tag == 'tr' and self.current is not None:
                    self.marked.append(self.current)
                    self.current = None
        right = archive()
        right['record']['transcript'][0]['summary'] = 'changed summary'
        right['record']['transcript'][3]['concerns'] = ['new concern']
        right['record']['transcript'][6]['verdict'] = 'REVIEW_NEEDED'
        right['record']['final_verdict'] = 'REVIEW_NEEDED'
        right['record']['verdict_counts'].update(OBSERVATION_ONLY=6, REVIEW_NEEDED=1)
        for candidate, expected in [(archive(), []), (right, ['M01', 'M04', 'M07'])]:
            parser = Rows()
            report = render_report(archive(), candidate, now=NOW)
            parser.feed(report)
            self.assertEqual([row[0] for row in parser.marked], expected)
            self.assertTrue(all(row[1] == '변경 있음' for row in parser.marked))
            self.assertEqual(report.count('>변경 없음</td>'), 7-len(expected))
            self.assertIn('role="region" tabindex="0" aria-label="발언별 변경 여부 표', report)
            self.assertNotIn('changed summary', report)
            self.assertNotIn('new concern', report)
        metadata_only = archive()
        metadata_only['record']['model'] = 'different-model'
        self.assertNotIn('<tr class="changed-row">', render_report(archive(), metadata_only, now=NOW))

    def test_navigation_targets_exist_once_for_inspection_and_comparison(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.targets = [], []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'id' in attrs:
                    self.ids.append(attrs['id'])
                if tag == 'a':
                    self.targets.append(attrs['href'])
        for right, section_count in [(None, 1), (archive(), 7)]:
            with self.subTest(comparison=right is not None):
                parser = Links()
                report = render_report(archive(), right, now=NOW)
                parser.feed(report)
                self.assertEqual(len(parser.ids), len(set(parser.ids)))
                self.assertEqual(len(parser.targets), section_count * 2)
                for target in parser.targets:
                    self.assertTrue(target.startswith('#'))
                    self.assertEqual(parser.ids.count(target[1:]), 1)
                self.assertIn('aria-label="보고서 목차"', report)
                self.assertNotIn('<script', report)

    def test_html_labels_are_localized_without_changing_machine_comparison_codes(self):
        left, right = archive(), archive()
        left['record']['market_source'] = right['record']['market_source'] = 'BYBIT_USDT_PERPETUAL_5M'
        right['record']['transcript'][0]['verdict'] = 'REVIEW_NEEDED'
        right['record']['final_verdict'] = 'REVIEW_NEEDED'
        right['record']['verdict_counts'].update(OBSERVATION_ONLY=6, REVIEW_NEEDED=1)
        before = deepcopy((left, right))
        report = render_report(left, right, now=NOW)
        for label in ('초기 분석', '상호 검토', '최종 결론', '추가 검토 필요', 'Bybit USDT 무기한 5분봉', '오프라인 테스트 (OFFLINE_FIXTURE)'):
            self.assertIn(label, report)
        compared = compare_archives(left, right, now=NOW)
        self.assertEqual(compared['statements'][0]['right_verdict'], 'REVIEW_NEEDED')
        self.assertEqual(compared['statements'][0]['phase'], 'ANALYSIS')
        self.assertEqual((left, right), before)

    def test_comparison_context_collects_actual_differences_without_a_quality_score(self):
        left, right = archive(), archive()
        left['record'].update(market_source='BYBIT_USDT_PERPETUAL_5M')
        right['record'].update(market_source='OKX_USDT_PERPETUAL_5M', model='other-model',
                               execution_mode='LIVE_PROVIDER', model_inference_performed=True,
                               source_generated_at_utc='2026-11-14T09:00:00Z', generated_at_utc='2026-11-14T11:00:30Z')
        before = deepcopy((left, right))
        result = compare_archives(left, right, now=NOW)
        self.assertEqual(result['comparison_context'], ['MARKET_SOURCE_CHANGED', 'MODEL_CHANGED',
            'EXECUTION_MODE_CHANGED', 'SOURCE_TIME_CHANGED', 'RIGHT_COMPLETION_EARLIER'])
        report = render_report(left, right, now=NOW)
        self.assertLess(report.index('비교 조건 요약'), report.index('<table>'))
        self.assertIn('시장 출처가 다름', report)
        self.assertIn('실행 모드가 다름', report)
        self.assertEqual((left, right), before)

    def test_unknown_and_matching_conditions_do_not_claim_verified_equal_inputs(self):
        left, right = archive(), archive()
        self.assertEqual(compare_archives(left, right, now=NOW)['comparison_context'], ['MARKET_SOURCE_UNKNOWN'])
        left['record']['market_source'] = right['record']['market_source'] = 'BYBIT_USDT_PERPETUAL_5M'
        self.assertEqual(compare_archives(left, right, now=NOW)['comparison_context'], [])
        self.assertIn('입력 데이터 동일성이나 실제 실행을 확인한 결과는 아닙니다', render_report(left, right, now=NOW))

    def test_all_verdict_transitions_have_conserved_counts_and_ids(self):
        for old in ('OBSERVATION_ONLY', 'REVIEW_NEEDED', 'INSUFFICIENT_DATA'):
            for new in ('OBSERVATION_ONLY', 'REVIEW_NEEDED', 'INSUFFICIENT_DATA'):
                with self.subTest(old=old, new=new):
                    left, right = archive(), archive()
                    for value, verdict in ((left, old), (right, new)):
                        value['record']['final_verdict'] = verdict
                        for s in value['record']['transcript']:
                            s['verdict'] = verdict
                        value['record']['verdict_counts'] = {k: 7 if k == verdict else 0 for k in value['record']['verdict_counts']}
                    result = compare_archives(left, right, now=NOW)
                    transitions = result['verdict_transitions']
                    self.assertEqual(len(transitions), 9)
                    self.assertEqual(sum(t['count'] for t in transitions), 7)
                    selected = next(t for t in transitions if (t['left_verdict'], t['right_verdict']) == (old, new))
                    self.assertEqual(selected['count'], 7)
                    self.assertEqual(selected['statement_ids'], [f'M{i:02}' for i in range(1, 8)])
                    self.assertEqual(sum(result['verdict_count_delta'].values()), 0)
                    self.assertEqual(result['verdict_count_delta'][new], 0 if old == new else 7)
                    self.assertEqual(result['verdict_count_delta'][old], 0 if old == new else -7)

    def test_mixed_transitions_distinguish_judgment_changes_from_prose(self):
        left, right = archive(), archive()
        left['record']['transcript'][0]['verdict'] = 'INSUFFICIENT_DATA'
        left['record']['verdict_counts'].update(OBSERVATION_ONLY=6, INSUFFICIENT_DATA=1)
        left['record']['final_verdict'] = 'INSUFFICIENT_DATA'
        right['record']['transcript'][2]['verdict'] = 'REVIEW_NEEDED'
        right['record']['verdict_counts'].update(OBSERVATION_ONLY=6, REVIEW_NEEDED=1)
        right['record']['final_verdict'] = 'REVIEW_NEEDED'
        result = compare_archives(left, right, now=NOW)
        changed = [t for t in result['verdict_transitions'] if t['count'] and t['left_verdict'] != t['right_verdict']]
        for verdict in left['record']['verdict_counts']:
            self.assertEqual(sum(t['count'] for t in result['verdict_transitions'] if t['left_verdict'] == verdict), left['record']['verdict_counts'][verdict])
            self.assertEqual(sum(t['count'] for t in result['verdict_transitions'] if t['right_verdict'] == verdict), right['record']['verdict_counts'][verdict])
        self.assertEqual({i for t in changed for i in t['statement_ids']}, {'M01', 'M03'})
        self.assertEqual(result['verdict_count_delta'], {'OBSERVATION_ONLY': 0, 'REVIEW_NEEDED': 1, 'INSUFFICIENT_DATA': -1})
        self.assertIn('판단 전환표', render_report(left, right, now=NOW))
        right = archive()
        right['record']['transcript'][0]['summary'] = 'different prose'
        report = render_report(archive(), right, now=NOW)
        self.assertIn('판단 전환 없음', report)
        self.assertNotIn('different prose', report)

    def test_changed_statement_summary_counts_overlapping_changes_once(self):
        left, right = archive(), archive()
        right['record']['transcript'][0].update(summary='changed', concerns=['new concern'])
        right['record']['transcript'][2]['verdict'] = 'REVIEW_NEEDED'
        right['record']['verdict_counts'].update(OBSERVATION_ONLY=6, REVIEW_NEEDED=1)
        right['record']['final_verdict'] = 'REVIEW_NEEDED'
        before = deepcopy((left, right))
        result = compare_archives(left, right, now=NOW)
        self.assertEqual(result['change_summary'], {'changed_statement_count': 2,
            'changed_statement_ids': ['M01', 'M03'], 'verdict_changed': 1,
            'summary_changed': 1, 'concerns_changed': 1})
        report = render_report(left, right, now=NOW)
        self.assertIn('변경된 발언 요약', report)
        self.assertIn('요약 · 우려', report)
        self.assertIn('발언별 변경 여부', report)
        self.assertNotIn('new concern', report)
        self.assertEqual((left, right), before)

    def test_metadata_changes_do_not_invent_statement_changes(self):
        left, right = archive(), archive()
        right['record']['model'] = 'changed-model'
        result = compare_archives(left, right, now=NOW)
        self.assertTrue(result['model_changed'])
        self.assertEqual(result['change_summary']['changed_statement_count'], 0)
        self.assertEqual(result['change_summary']['changed_statement_ids'], [])
        self.assertIn('변경된 발언 없음', render_report(left, right, now=NOW))
        self.assertEqual(len(result['statements']), 7)

    def test_time_relations_preserve_argument_order_including_reverse_and_equal_times(self):
        left, right = archive(), archive()
        right['record']['source_generated_at_utc'] = '2026-11-14T10:05:00Z'
        right['record']['generated_at_utc'] = '2026-11-14T11:02:00Z'
        result = compare_archives(left, right, now=NOW)
        self.assertEqual(result['time_relation']['source'],
                         {'order': 'RIGHT_LATER', 'right_minus_left_seconds': 300.0})
        self.assertEqual(result['time_relation']['completion']['right_minus_left_seconds'], 60.0)
        reversed_result = compare_archives(right, left, now=NOW)
        self.assertEqual(reversed_result['time_relation']['source'],
                         {'order': 'RIGHT_EARLIER', 'right_minus_left_seconds': -300.0})
        self.assertEqual(reversed_result['left']['generated_at_utc'], right['record']['generated_at_utc'])
        equal = compare_archives(left, left, now=NOW)
        self.assertEqual(equal['time_relation']['completion'],
                         {'order': 'SAME_TIME', 'right_minus_left_seconds': 0.0})
        self.assertIn('오른쪽 기록이 먼저', render_report(right, left, now=NOW))
        self.assertIn('-300.0', render_report(right, left, now=NOW))

    def test_source_and_completion_order_can_differ_and_model_changes_stay_explicit(self):
        left, right = archive(), archive()
        right['record'].update(source_generated_at_utc='2026-11-14T09:00:00Z',
                               generated_at_utc='2026-11-14T11:02:00Z', model='other-model')
        before = deepcopy((left, right))
        result = compare_archives(left, right, now=NOW)
        self.assertEqual(result['time_relation']['source']['order'], 'RIGHT_EARLIER')
        self.assertEqual(result['time_relation']['completion']['order'], 'RIGHT_LATER')
        self.assertTrue(result['model_changed'])
        self.assertEqual((left, right), before)
        self.assertFalse(compare_archives(left, left, now=NOW)['model_changed'])

    def test_html_report_escapes_metadata_and_preserves_provenance_and_changes(self):
        left, right = archive(), archive()
        right['record']['model'] = '<script>alert("model")</script>'
        right['record']['transcript'][0]['summary'] = 'changed private statement'
        report = render_report(left, right, now=NOW)
        self.assertIn('&lt;script&gt;', report)
        self.assertNotIn('<script>', report)
        self.assertIn('default-src', report)
        self.assertIn('OFFLINE_FIXTURE', report)
        self.assertIn('UNKNOWN', report)
        self.assertIn('M07', report)
        self.assertIn('변경', report)
        self.assertNotIn('private statement', report)
        self.assertNotIn('fetch(', report)
        self.assertNotIn('src=', report)
        self.assertIn('저장 기록', render_report(left, now=NOW))
        invalid = archive()
        invalid['orders_enabled'] = True
        with self.assertRaises(ValueError):
            render_report(invalid, right, now=NOW)

    def test_historical_record_and_null_metadata_are_supported(self):
        value = archive()
        self.assertEqual(validate_archive(value, now=NOW), value)
        compared = compare_archives(value, value, now=NOW)
        self.assertEqual(compared['market_comparison'], 'UNKNOWN')
        self.assertFalse(compared['final_verdict_changed'])
        self.assertTrue(all(not row['summary_changed'] for row in compared['statements']))

    def test_comparison_tracks_separate_verdict_text_concern_and_provenance_changes(self):
        left, right = archive(), archive()
        right['record'].update(execution_mode='LIVE_PROVIDER', model_inference_performed=True,
                               market_source='BYBIT_USDT_PERPETUAL_5M', final_verdict='REVIEW_NEEDED')
        right['record']['transcript'][2].update(verdict='REVIEW_NEEDED', concerns=['data gap'])
        right['record']['transcript'][0]['summary'] = 'different private statement'
        right['record']['verdict_counts'].update(OBSERVATION_ONLY=6, REVIEW_NEEDED=1)
        before = deepcopy((left, right))
        result = compare_archives(left, right, now=NOW)
        self.assertTrue(result['execution_mode_changed'])
        self.assertTrue(result['final_verdict_changed'])
        self.assertTrue(result['statements'][0]['summary_changed'])
        self.assertFalse(result['statements'][0]['verdict_changed'])
        self.assertTrue(result['statements'][2]['concerns_changed'])
        self.assertTrue(result['statements'][2]['verdict_changed'])
        self.assertNotIn('private statement', json.dumps(result))
        self.assertEqual((left, right), before)

    def test_market_sources_are_not_silently_equated(self):
        left, right = archive(), archive()
        left['record']['market_source'] = right['record']['market_source'] = 'BYBIT_USDT_PERPETUAL_5M'
        self.assertEqual(compare_archives(left, right, now=NOW)['market_comparison'], 'SAME')
        right['record']['market_source'] = 'OKX_USDT_PERPETUAL_5M'
        self.assertEqual(compare_archives(left, right, now=NOW)['market_comparison'], 'DIFFERENT')

    def test_corrupted_metadata_structure_and_counts_are_rejected(self):
        mutations = [lambda v: v.update(extra='private'), lambda v: v.update(orders_enabled=0),
                     lambda v: v.update(archived_at_utc='2099-01-01T00:00:00Z'),
                     lambda v: v['record'].update(model_inference_performed=True),
                     lambda v: v['record'].update(workflow_execution_id='invalid'),
                     lambda v: v['record'].update(generated_at_utc='2026-11-14T09:00:00Z'),
                     lambda v: v['record'].update(started_at_utc='2026-11-14T11:00:00'),
                     lambda v: v['record']['verdict_counts'].update(REVIEW_NEEDED=True),
                     lambda v: v['record']['verdict_counts'].update(OBSERVATION_ONLY=6),
                     lambda v: v['record']['transcript'].pop(),
                     lambda v: v['record']['transcript'][0].update(id='M02'),
                     lambda v: v['record']['transcript'][0].update(agent='COMMANDER'),
                     lambda v: v['record']['transcript'][0].update(extra='private'),
                     lambda v: v['record']['transcript'][0].update(summary='x'*1601),
                     lambda v: v['record']['transcript'][0].update(concerns=['x']*9)]
        for mutate in mutations:
            value = archive()
            mutate(value)
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                validate_archive(value, now=NOW)

    def test_reader_rejects_duplicate_keys_and_oversize_without_modification(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'archive.json'
            for raw in (b'{"version":1,"version":2}', b'x'*(MAX_BYTES+1), b'private invalid data'):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    read_archive(path, now=NOW)
                self.assertEqual(path.read_bytes(), raw)

    def test_real_cli_inspection_comparison_and_sanitized_failure_are_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            left, right = Path(folder)/'left.json', Path(folder)/'right.json'
            left.write_text(json.dumps(archive()))
            right.write_text(json.dumps(archive()))
            originals = (left.read_bytes(), right.read_bytes())
            command = [sys.executable, str(Path(__file__).with_name('ai_meeting_archive.py'))]
            for inputs, version in (([left], 'MEETING_ARCHIVE_INSPECTION_1'),
                                    ([left, right], 'MEETING_ARCHIVE_COMPARISON_1')):
                result = subprocess.run([*command, *map(str, inputs)], cwd=folder,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                output = json.loads(result.stdout)
                self.assertEqual(output['version'], version)
                self.assertIs(output['orders_enabled'], False)
                self.assertNotIn('private statement', result.stdout)
            self.assertEqual((left.read_bytes(), right.read_bytes()), originals)
            for inputs in ([left], [left, right]):
                html_result = subprocess.run([*command, *map(str, inputs), '--format', 'html'],
                                             cwd=folder, capture_output=True, text=True, timeout=5)
                self.assertEqual(html_result.returncode, 0, html_result.stderr)
                self.assertTrue(html_result.stdout.startswith('<!doctype html>'))
                self.assertNotIn('private statement', html_result.stdout)
            self.assertEqual((left.read_bytes(), right.read_bytes()), originals)
            right.write_text('private broken record')
            failed = subprocess.run([*command, str(left), str(right)], cwd=folder,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(failed.stdout, '')
            self.assertNotIn('private broken record', failed.stderr)
            self.assertNotIn('Traceback', failed.stderr)
            self.assertEqual(set(Path(folder).iterdir()), {left, right})
