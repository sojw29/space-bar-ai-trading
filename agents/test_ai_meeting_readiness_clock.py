from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_meeting_readiness import assess_readiness, check_file, render_summary, STAGES
from test_v233_agent_research_runtime import source, NOW


class ReadinessClockTests(unittest.TestCase):
    def test_input_expiring_during_preparation_is_not_ready(self):
        brief = source()
        brief['source_generated_at_utc'] = (NOW-timedelta(hours=8)+timedelta(seconds=1)).isoformat()
        brief['generated_at_utc'] = (NOW-timedelta(seconds=1)).isoformat()
        with patch('ai_meeting_readiness.datetime') as date:
            date.now.side_effect = [NOW, NOW, NOW+timedelta(seconds=2)] + [NOW+timedelta(seconds=2)]*8
            report = assess_readiness(brief)
        self.assertEqual(report['status'], 'BLOCKED')
        self.assertEqual(report['stage'], 'HANDOFF')
        self.assertEqual(report['checks'][-1]['status'], 'FAIL')

    def brief_near_expiry(self):
        brief = source()
        brief['source_generated_at_utc'] = (NOW-timedelta(hours=8)+timedelta(seconds=1)).isoformat()
        brief['generated_at_utc'] = (NOW-timedelta(seconds=1)).isoformat()
        return brief

    def test_expiry_after_all_stages_pass_still_blocks_final_readiness(self):
        times = iter([NOW]*6+[NOW+timedelta(seconds=2)])
        report = assess_readiness(self.brief_near_expiry(), clock=lambda: next(times))
        self.assertEqual(report['status'], 'BLOCKED')
        self.assertEqual(report['stage'], 'PREFLIGHT')
        self.assertEqual(report['checks'][-1], {'stage': 'PREFLIGHT', 'status': 'FAIL'})
        self.assertEqual(report['prepared_agent_count'], 0)
        self.assertIn('BLOCKED', render_summary(report, now=NOW+timedelta(seconds=2)))

    def test_inclusive_expiry_boundary_and_actual_completion_timestamp(self):
        times = iter([NOW]*6+[NOW+timedelta(seconds=1)])
        report = assess_readiness(self.brief_near_expiry(), clock=lambda: next(times))
        self.assertEqual(report['status'], 'INPUTS_READY')
        self.assertEqual(report['generated_at_utc'], (NOW+timedelta(seconds=1)).isoformat())
        render_summary(report, now=NOW+timedelta(seconds=1))
        with self.assertRaises(ValueError):
            render_summary(report, now=NOW+timedelta(seconds=1, microseconds=1))

    def test_clock_rollback_before_stage_or_after_last_stage_is_explicitly_blocked(self):
        for values, stage in (([NOW, NOW, NOW-timedelta(seconds=1)], 'HANDOFF'),
                              ([NOW]*6+[NOW-timedelta(seconds=1)], 'PREFLIGHT')):
            times = iter(values)
            report = assess_readiness(source(), clock=lambda: next(times))
            self.assertEqual(report['status'], 'BLOCKED')
            self.assertEqual(report['stage'], stage)
            self.assertEqual(report['error_code'], 'CLOCK_CHANGED')
            self.assertIn('CLOCK_CHANGED', render_summary(report, now=NOW))

    def test_file_entrypoint_does_not_freeze_clock_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'brief.json'
            path.write_text(json.dumps(self.brief_near_expiry()))
            with patch('ai_meeting_readiness.datetime') as date:
                date.now.side_effect = [NOW]*3+[NOW+timedelta(seconds=2)]*8
                report = check_file(path)
            self.assertEqual(report['status'], 'BLOCKED')
            self.assertEqual(report['stage'], 'HANDOFF')

    def test_every_stage_receives_current_time_while_fixed_now_remains_replayable(self):
        times = iter(NOW+timedelta(seconds=i) for i in range(7))
        report = assess_readiness(source(), clock=lambda: next(times))
        self.assertEqual(report['status'], 'INPUTS_READY')
        self.assertEqual(report['generated_at_utc'], (NOW+timedelta(seconds=6)).isoformat())
        self.assertEqual([c['stage'] for c in report['checks']], list(STAGES))
        self.assertEqual(assess_readiness(source(), now=NOW)['generated_at_utc'], NOW.isoformat())
        with self.assertRaises(ValueError):
            assess_readiness(source(), now=NOW, clock=lambda: NOW)


if __name__ == '__main__':
    unittest.main()
