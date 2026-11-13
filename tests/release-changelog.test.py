#!/usr/bin/env python3
# Copyright (C) 2026 wfire06100
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_changes', ROOT / 'tools/tee/release_changes.py')
notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notes)
A, B, C = 'a' * 40, 'b' * 40, 'c' * 40


class ReleaseNotesTests(unittest.TestCase):
    def test_sections(self):
        text = '## [Unreleased]\n### Added\n- New\n## v1\n- Old\n'
        self.assertEqual(notes.section(text, 'Unreleased'), '### Added\n- New')
        self.assertEqual(notes.section(text, 'missing'), '')

    def test_unchanged_engine(self):
        with patch.object(notes, 'api') as api:
            self.assertEqual(notes.commits('owner/engine', A, A), [])
            api.assert_not_called()

    def test_pagination(self):
        pages = [dict(status='ahead', total_commits=2, commits=[{'sha': A}]),
                 dict(status='ahead', total_commits=2, commits=[{'sha': B}])]
        with patch.object(notes, 'api', side_effect=pages) as api:
            self.assertEqual(len(notes.commits('owner/repo', A, C)), 2)
            self.assertEqual(api.call_count, 2)

    def test_diverged_history_fails(self):
        with patch.object(notes, 'api', return_value={'status': 'diverged'}):
            with self.assertRaises(ValueError):
                notes.commits('owner/repo', A, B)

    def test_commit_body_is_escaped(self):
        change = {'sha': B, 'commit': {'message': 'feat: update\n\n<script>bad</script>'}}
        with patch.object(notes, 'commits', return_value=[change]):
            text = notes.commit_notes('owner/repo', A, B)
            self.assertIn('&lt;script&gt;', text)
            self.assertNotIn('<script>', text)

    def test_no_repeated_unreleased(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = '## [Unreleased]\n### Fixed\n- Sync notes\n'
            (root / notes.CHANGELOG).write_text(text)
            with patch.object(notes, 'download', return_value=text.encode()):
                self.assertEqual(notes.curated(root, 'v2', 'owner/repo', A), '')
            with patch.object(notes, 'download', return_value=None):
                self.assertIn('Sync notes', notes.curated(root, 'v2', 'owner/repo', A))

    def test_initial_release(self):
        info = {'sourceCommit': A, 'versionCode': 1, 'engine': {'sourceCommit': B, 'version': 'v1'}}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(notes, 'api', return_value=None):
                text = notes.release_changes(Path(directory), Path(directory), 'v1', info, 'owner/repo')
                self.assertIn('Initial published baseline', text)

    def test_existing_release_is_not_overwritten(self):
        info = {'sourceCommit': A, 'engine': {'sourceCommit': B}}
        with patch.object(notes, 'api', return_value={'tag_name': 'v1'}):
            with self.assertRaises(ValueError):
                notes.release_changes(Path('.'), Path('.'), 'v1', info, 'owner/repo')


if __name__ == '__main__':
    unittest.main()
