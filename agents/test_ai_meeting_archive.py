from copy import deepcopy
from datetime import datetime, timezone
import json
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
