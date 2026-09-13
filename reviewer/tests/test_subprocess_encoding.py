"""Keep UTF-8 patches and arbitrary Git bytes intact on Windows."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from control_plane_reviewer.handoff import _git
from control_plane_reviewer.intake import _command
from control_plane_reviewer.review import _run


class SubprocessEncodingTests(unittest.TestCase):
    def test_text_commands_preserve_unicode_and_undecodable_bytes(self):
        payload = 'Cost basis — café · €'.encode('utf-8') + b'\xff'
        expected = payload.decode('utf-8', errors='surrogateescape')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv = (sys.executable, '-c', f'import sys; sys.stdout.buffer.write({payload!r})')
            self.assertEqual(_command(argv, root), expected)
            self.assertEqual(_run(root, argv).stdout, expected)
            subprocess.run(('git', 'init', '-q', str(root)), check=True)
            blob = subprocess.run(
                ('git', 'hash-object', '-w', '--stdin'), cwd=root,
                input=payload, capture_output=True, check=True,
            ).stdout.decode('ascii').strip()
            self.assertEqual(_git(root, 'cat-file', 'blob', blob), expected)

    def test_binary_review_output_remains_exact_bytes(self):
        payload = b'\x00\xff\r\n\xc3\xa9'
        with tempfile.TemporaryDirectory() as directory:
            argv = (sys.executable, '-c', f'import sys; sys.stdout.buffer.write({payload!r})')
            self.assertEqual(_run(Path(directory), argv, binary=True).stdout, payload)
