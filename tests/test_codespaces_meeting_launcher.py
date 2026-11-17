"""Exercise launcher argument handling without starting a server or model."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('bash'), 'Bash required')
class CodespacesMeetingLauncherTests(unittest.TestCase):
    def run_launcher(self, args, occupied=False, python_exit=0):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.devcontainer').mkdir()
            script = root / '.devcontainer' / 'start-room.sh'
            shutil.copyfile(ROOT / '.devcontainer' / 'start-room.sh', script)
            binaries = root / 'bin'
            binaries.mkdir()
            (binaries / 'curl').write_text('#!/bin/sh\nexit ' + ('0' if occupied else '1') + '\n')
            (binaries / 'python').write_text(
                '#!' + sys.executable + '\n'
                'import json, os, pathlib, sys\n'
                'pathlib.Path(os.environ["CAPTURE"]).write_text(json.dumps({"args":sys.argv[1:],"cwd":os.getcwd()}))\n'
                'sys.exit(int(os.environ["PYTHON_EXIT"]))\n')
            for binary in binaries.iterdir():
                binary.chmod(0o755)
            capture = root / 'capture.json'
            env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ.get('PATH', ''),
                       CAPTURE=str(capture), PYTHON_EXIT=str(python_exit))
            result = subprocess.run([shutil.which('bash'), str(script), *args],
                                    cwd='/', env=env, capture_output=True, text=True, timeout=5)
            captured = json.loads(capture.read_text()) if capture.exists() else None
            return result, captured, str(root)

    def test_session_path_is_one_argument_and_uses_repository_root(self):
        result, captured, root = self.run_launcher(['--meeting-session', 'reports/session with spaces'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(captured['args'], ['-u', 'agents/dashboard_api_v28.py', '--port', '8765',
                                            '--meeting-session', 'reports/session with spaces'])
        self.assertEqual(captured['cwd'], root)

    def test_session_startup_error_is_propagated(self):
        result, captured, _ = self.run_launcher(['--meeting-session', 'missing'], python_exit=2)
        self.assertEqual(result.returncode, 2)
        self.assertIsNotNone(captured)

    def test_occupied_port_never_silently_changes_session(self):
        result, captured, _ = self.run_launcher(['--meeting-session', 'reports/new'], occupied=True)
        self.assertEqual(result.returncode, 1)
        self.assertIsNone(captured)
        self.assertIn('existing session was not changed', result.stderr)

    def test_default_existing_server_remains_reusable(self):
        result, captured, _ = self.run_launcher([], occupied=True)
        self.assertEqual(result.returncode, 0)
        self.assertIsNone(captured)
        self.assertIn('already running', result.stdout)

    def test_invalid_options_fail_before_server_detection(self):
        for args in (['--meeting-session'], ['--meeting-session', ''],
                     ['--port', '9000'], ['--meeting-session', 'x', '--enable-live']):
            with self.subTest(args=args):
                result, captured, _ = self.run_launcher(args, occupied=True)
                self.assertEqual(result.returncode, 2)
                self.assertIsNone(captured)
                self.assertIn('Usage:', result.stderr)
