#!/usr/bin/env python3
# Copyright (C) 2026 wfire06100
# SPDX-License-Identifier: Apache-2.0
'Verify the current build and prepare notes without changing its version suffix.'
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote


def prepare(root, directory, version, expected_digest, source, repository):
    if not re.fullmatch(r'v\d+\.\d+\.\d+-b\d+\.\d+', version):
        raise ValueError('Unexpected packaged version')
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('Invalid source revision')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid repository')
    candidates = list(directory.rglob('TOPG-*.zip'))
    if len(candidates) != 1:
        raise ValueError('Expected exactly one TOPG module ZIP')
    archive_path = candidates[0].resolve()
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if digest != expected_digest:
        raise ValueError('Downloaded ZIP checksum mismatch')
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError('Invalid ZIP CRC')
        props = dict(line.split('=', 1) for line in archive.read('module.prop').decode().splitlines()
                     if line.strip() and not line.lstrip().startswith('#'))
        info = json.loads(archive.read('build-info.json'))
        if props.get('id') != 'COPG-VD' or props.get('name') != 'TOPG':
            raise ValueError('Not a TOPG module')
        if props['version'] != version or info['version'] != version:
            raise ValueError('Version mismatch')
        if str(info['versionCode']) != props['versionCode'] or info['sourceCommit'] != source:
            raise ValueError('Build provenance mismatch')
    if archive_path.name != 'TOPG-' + version + '.zip':
        raise ValueError('ZIP filename mismatch')
    checksum = archive_path.with_name(archive_path.name + '.sha256')
    checksum.write_text(digest + '  ' + archive_path.name + '\n')
    notes = directory / 'RELEASE_NOTES.md'
    text = f'''# TOPG {version}

COPG-VD and TEESimulator-RS integration maintained by wfire06100.

## Features

- Dedicated TEE tab with application targeting in Auto, Generate (`!`), or Hack (`?`) mode.
- Personal keybox import and scheduled XML/base64 downloads.
- Data migration or initialization with backups and preservation of persistent keys.
- Shared navigation controller across all six tabs and portable locking for TEE operations.
- TOPG manager update channel with a release-hosted update manifest and changelog.

## Installation and limitations

Download `{archive_path.name}`, not GitHub's automatically generated source code archives. Back up your data, follow the installer instructions, and reboot. This integration requires Android 10 or later.

Automated tests and ZIP validation do not certify real-device compatibility. No specific Play Integrity or Wallet outcome is guaranteed. Keybox structure validation does not establish cryptographic validity or non-revocation. The default HTTP mirror is not authenticated.

## Build information

- Full version: `{version}` (suffix preserved).
- Version code: `{props['versionCode']}`.
- TOPG commit: `{source}`.
- Engine: TEESimulator-RS `{info['engine']['version']}`.
- Engine commit: `{info['engine']['sourceCommit']}`.
- SHA-256: `{digest}`.

## Credits and licenses

TOPG: wfire06100. COPG/COPG-VD: AlirezaParsi and VD171. Original TEESimulator: JingMatrix. TEESimulator-RS: Enginex0 and contributors. Apache-2.0, GPL-3.0, and applicable component license and attribution notices are preserved. See `TOPG-LICENSING.md` in the module for component licensing and corresponding-source locations. These measures are not a legal certification of compliance.
'''
    photos = sorted(p for p in (root / 'screenshots/topg').glob('*')
                    if p.is_file() and p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'))
    title = 'TOPG screenshots'
    if not photos:
        title = 'COPG-VD base screenshots'
        photos = [root / 'screenshots' / (name + '.png') for name in ('device', 'spoofing', 'system', 'tools')]
        photos = [p for p in photos if p.is_file()]
    if photos:
        text += '\n## ' + title + '\n\n'
        for i, photo in enumerate(photos, 1):
            url = f'https://raw.githubusercontent.com/{repository}/{source}/' + quote(photo.relative_to(root).as_posix())
            text += f'![{title} — {i}]({url})\n\n'
    notes.write_text(text)
    return archive_path, checksum.resolve(), notes.resolve()


if __name__ == '__main__':
    from release_changes import release_changes
    root = Path('.').resolve()
    subprocess.run([sys.executable, str(root / 'tests/release-changelog.test.py')], check=True)
    archive, checksum, notes = prepare(root, Path('release-files').resolve(),
        os.environ['VERSION'], os.environ['EXPECTED_SHA256'], os.environ['GITHUB_SHA'], os.environ['GITHUB_REPOSITORY'])
    with zipfile.ZipFile(archive) as packaged:
        info = json.loads(packaged.read('build-info.json'))
    changes = release_changes(root, notes.parent, os.environ['VERSION'], info, os.environ['GITHUB_REPOSITORY'])
    text = notes.read_text()
    anchor = '\n## Features\n'
    if text.count(anchor) != 1:
        raise ValueError('Release notes insertion anchor changed')
    notes.write_text(text.replace(anchor, '\n' + changes + anchor, 1))
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write(f'zip={archive}\nchecksum={checksum}\nnotes={notes}\n')
