"""Setup checks must never call providers, publish files, or expose secrets."""
import json
from datetime import timedelta
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_meeting_setup import check_setup
from test_v240_provider_transport_preflight import request, NOW


class SetupTests(unittest.TestCase):
    def test_valid_input_checks_configuration_without_provider_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'bundle.json'
            source.write_text(json.dumps(request()), encoding='utf-8')
            original = source.read_bytes()
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'private-test-key'}):
                with patch('ai_meeting_runtime.OpenAIProvider.complete', side_effect=AssertionError('model call')) as complete:
                    result = check_setup(source, 'test-model', now=NOW)
            self.assertEqual(result['status'], 'LOCAL_SETUP_VALID')
            self.assertFalse(result['provider_verified'])
            self.assertFalse(result['orders_enabled'])
            self.assertEqual(result['model_calls_performed'], 0)
            complete.assert_not_called()
            self.assertNotIn('private-test-key', json.dumps(result))
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [source])

    def test_missing_key_and_invalid_model_are_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'bundle.json'
            source.write_text(json.dumps(request()), encoding='utf-8')
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(check_setup(source, 'model', now=NOW)['error_code'], 'OPENAI_API_KEY_REQUIRED')
            self.assertEqual(check_setup(source, '', now=NOW)['error_code'], 'MODEL_REQUIRED')

    def test_invalid_input_is_blocked_before_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'bundle.json'
            for raw in [b'{secret input', b'null', b'x' * 65537]:
                source.write_bytes(raw)
                with patch('ai_meeting_setup.OpenAIProvider', side_effect=AssertionError('constructed')):
                    result = check_setup(source, 'model', now=NOW)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertEqual(result['model_calls_performed'], 0)
                self.assertNotIn('secret input', json.dumps(result))
            source.write_text(json.dumps(request()), encoding='utf-8')
            with patch('ai_meeting_setup.OpenAIProvider', side_effect=AssertionError('constructed')):
                result = check_setup(source, 'model', now=NOW + timedelta(hours=9))
            self.assertEqual(result['status'], 'BLOCKED')
            source.unlink()
            self.assertEqual(check_setup(source, 'model', now=NOW)['error_code'], 'FILE_ERROR')


if __name__ == '__main__':
    unittest.main()
