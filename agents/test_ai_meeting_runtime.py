import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from urllib.error import HTTPError

from test_v240_provider_transport_preflight import request, NOW
from ai_meeting_runtime import (run_meeting, OpenAIProvider, MeetingError,
                                validate_statement, publish_report, NoRedirect)


def statement(verdict="OBSERVATION_ONLY"):
    return {"summary": "제공된 자료의 관측 결과", "concerns": ["과거 자료이며 예측 검증 없음"], "verdict": verdict}


class Fixture:
    def __init__(self):
        self.calls = []

    def complete(self, agent, phase, context):
        self.calls.append((agent, phase, context))
        return statement()


class MeetingTests(unittest.TestCase):
    def test_seven_calls_and_real_peer_context_without_fixture_inference_claim(self):
        fixture = Fixture()
        bundle = request()
        bundle['requests'][0]['facts']['unexpected'] = 'do not transmit'
        # All agents must still receive the same facts for input preflight.
        for r in bundle['requests'][1:]:
            r['facts']['unexpected'] = 'do not transmit'
        result = run_meeting(bundle, fixture, clock=lambda: NOW)
        self.assertEqual(len(fixture.calls), 7)
        self.assertEqual([c[:2] for c in fixture.calls],
                         [(a, 'ANALYSIS') for a in ('ATLAS', 'QUANT', 'GUARDIAN')] +
                         [(a, 'PEER_REVIEW') for a in ('ATLAS', 'QUANT', 'GUARDIAN')] +
                         [('COMMANDER', 'CONCLUSION')])
        self.assertEqual(len(fixture.calls[3][2]['analyses']), 3)
        self.assertEqual(len(fixture.calls[-1][2]['discussion']), 6)
        self.assertNotIn('unexpected', json.dumps(fixture.calls))
        self.assertFalse(result['model_inference_performed'])
        self.assertEqual(result['execution_mode'], 'OFFLINE_FIXTURE')
        self.assertFalse(result['orders_enabled'])
        self.assertEqual(result['trade_authorization'], 'DENIED')

    def test_invalid_source_stops_before_any_call(self):
        for mutation in ('stale', 'orders', 'different_facts'):
            with self.subTest(mutation=mutation):
                bundle, fixture = request(), Fixture()
                if mutation == 'stale':
                    bundle['source_generated_at_utc'] = (NOW-timedelta(hours=9)).isoformat()
                elif mutation == 'orders':
                    bundle['orders_enabled'] = True
                else:
                    bundle['requests'][1]['facts']['markets'][0]['volume_ratio_20'] = 9
                with self.assertRaises(ValueError):
                    run_meeting(bundle, fixture, clock=lambda: NOW)
                self.assertEqual(fixture.calls, [])

    def test_invalid_response_stops_pipeline(self):
        fixture = Fixture()
        fixture.complete = MagicMock(return_value={'summary': 'invalid'})
        with self.assertRaises(MeetingError):
            run_meeting(request(), fixture, clock=lambda: NOW)
        self.assertEqual(fixture.complete.call_count, 1)

    def test_guardian_and_insufficient_evidence_cannot_be_overruled(self):
        for objection in ('REVIEW_NEEDED', 'INSUFFICIENT_DATA'):
            fixture = Fixture()
            fixture.complete = lambda a, p, c: statement(objection if a == 'GUARDIAN' else 'OBSERVATION_ONLY')
            result = run_meeting(request(), fixture, clock=lambda: NOW)
            self.assertEqual(result['final_verdict'], objection)
            self.assertEqual(result['transcript'][-1]['verdict'], 'OBSERVATION_ONLY')

    def test_source_expiring_during_meeting_stops_later_calls(self):
        fixture, ticks = Fixture(), iter([NOW, NOW, NOW+timedelta(hours=9)])
        with self.assertRaises(ValueError):
            run_meeting(request(), fixture, clock=lambda: next(ticks))
        self.assertEqual(len(fixture.calls), 1)

    def test_bad_text_and_additional_fields_are_rejected(self):
        for value in ({**statement(), 'orders_enabled': True}, statement('BUY'),
                      {**statement(), 'summary': ' '}, {**statement(), 'concerns': ['x']*9}):
            with self.subTest(value=value), self.assertRaises(MeetingError):
                validate_statement(value)

    def test_publish_is_atomic_and_does_not_follow_destination_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source.json'
            source.write_text('original')
            target = Path(directory)/'ai_meeting.json'
            try:
                target.symlink_to(source)
            except OSError:
                self.skipTest('symlinks unavailable')
            publish_report({'complete': True}, target)
            self.assertEqual(source.read_text(), 'original')
            self.assertEqual(json.loads(target.read_text()), {'complete': True})
            self.assertFalse(target.is_symlink())
            self.assertEqual(list(Path(directory).glob('.ai-meeting-*')), [])


class TransportTests(unittest.TestCase):
    def test_disabled_missing_key_and_model_never_open_network(self):
        with patch('ai_meeting_runtime.build_opener') as opener:
            for kwargs in ({}, {'enabled': True}, {'enabled': True, 'model': 'test', 'api_key': ''}):
                with self.assertRaises(MeetingError):
                    OpenAIProvider(**kwargs)
            opener.assert_not_called()

    def provider(self):
        return OpenAIProvider(enabled=True, model='test-model', api_key='test-key')

    def response(self, content=None, finish='stop', refusal=None):
        return json.dumps({'choices': [{'finish_reason': finish, 'message': {
            'content': json.dumps(statement()) if content is None else content,
            'refusal': refusal}}]}).encode()

    def test_transport_contract_and_successful_live_provenance(self):
        with patch('ai_meeting_runtime.build_opener') as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.read.return_value = self.response()
            result = run_meeting(request(), self.provider(), clock=lambda: NOW)
            self.assertTrue(result['model_inference_performed'])
            self.assertEqual(result['execution_mode'], 'LIVE_PROVIDER')
            self.assertEqual(opener.return_value.open.call_count, 7)
            req = opener.return_value.open.call_args.args[0]
            payload = json.loads(req.data)
            self.assertEqual(req.full_url, 'https://api.openai.com/v1/chat/completions')
            self.assertEqual(payload['response_format']['type'], 'json_schema')
            self.assertFalse(payload['store'])
            self.assertNotIn('tools', payload)
            self.assertNotIn('test-key', json.dumps(result))
            self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'], 30)

    def test_http_failure_redacts_provider_body_and_never_retries(self):
        with patch('ai_meeting_runtime.build_opener') as opener:
            opener.return_value.open.side_effect = HTTPError('url', 401, 'test-key', {}, None)
            with self.assertRaisesRegex(MeetingError, '^PROVIDER_AUTHENTICATION_FAILED$'):
                self.provider().complete('ATLAS', 'ANALYSIS', {})
            self.assertEqual(opener.return_value.open.call_count, 1)

    def test_refusal_truncation_oversize_and_invalid_json_fail_closed(self):
        for raw in (self.response(finish='length'), self.response(refusal='no'),
                    self.response(content='not json'), b'x'*65537, b'{}', b'[]',
                    b'{"choices":["unexpected"]}', b'{"choices":[{"message":[]}]}'):
            with self.subTest(raw=raw[:80]), patch('ai_meeting_runtime.build_opener') as opener:
                opener.return_value.open.return_value.__enter__.return_value.read.return_value = raw
                with self.assertRaises(MeetingError):
                    self.provider().complete('ATLAS', 'ANALYSIS', {})

    def test_redirects_are_not_followed(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example'))


if __name__ == '__main__':
    unittest.main()
