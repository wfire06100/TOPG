#!/usr/bin/env python3
# Copyright (C) 2026 wfire06100
# SPDX-License-Identifier: Apache-2.0
"""Release-scoped TOPG notes. Network failures abort rather than omit changes."""
import hashlib
import html
import io
import json
import os
import re
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

API = 'https://api.github.com/repos/'
ENGINE_REPOSITORY = 'wfire06100/TEESimulator-RS'
CHANGELOG = 'TOPG-CHANGELOG.md'


def download(url, missing=False):
    headers = {'User-Agent': 'TOPG-release-notes', 'Accept': 'application/vnd.github+json'}
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token and url.startswith('https://api.github.com/'):
        headers['Authorization'] = 'Bearer ' + token
    try:
        with urlopen(Request(url, headers=headers), timeout=60) as response:
            data = response.read(256 * 1024 * 1024 + 1)
            if len(data) > 256 * 1024 * 1024:
                raise ValueError('Release response too large')
            return data
    except HTTPError as error:
        if missing and error.code == 404:
            return None
        raise


def api(repository, endpoint, missing=False):
    raw = download(API + repository + '/' + endpoint, missing)
    return None if raw is None else json.loads(raw)


def revision(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{40}', value):
        raise ValueError('Invalid recorded commit')
    return value


def section(text, name):
    match = re.search(r'^## \[?' + re.escape(name) + r'\]?(?:[ \t]+[^\n]*)?[ \t]*$', text, re.M)
    if not match:
        return ''
    rest = text[match.end():]
    end = re.search(r'^## ', rest, re.M)
    return (rest[:end.start()] if end else rest).strip()


def curated(root, version, repository, previous_sha):
    path = root / CHANGELOG
    text = path.read_text() if path.exists() else ''
    explicit = section(text, version)
    if explicit:
        return explicit
    current = section(text, 'Unreleased')
    if not current or not previous_sha:
        return current
    raw = download(f'https://raw.githubusercontent.com/{repository}/{previous_sha}/{CHANGELOG}', missing=True)
    previous = section(raw.decode() if raw is not None else '', 'Unreleased')
    return current if current != previous else ''


def previous_build(repository, release):
    assets = [a for a in release['assets'] if re.fullmatch(r'TOPG-.*\.zip', a['name'])]
    if len(assets) != 1:
        raise ValueError('Previous release needs exactly one TOPG ZIP')
    asset = assets[0]
    raw = download(asset['browser_download_url'])
    digest = asset.get('digest')
    if digest and digest != 'sha256:' + hashlib.sha256(raw).hexdigest():
        raise ValueError('Previous release asset digest mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        info = json.loads(archive.read('build-info.json'))
    if info['version'] != release['tag_name']:
        raise ValueError('Previous ZIP does not match release tag')
    revision(info['sourceCommit'])
    revision(info['engine']['sourceCommit'])
    return info


def commits(repository, base, head):
    revision(base)
    revision(head)
    if base == head:
        return []
    result = []
    page = 1
    while True:
        data = api(repository, f'compare/{base}...{head}?per_page=100&page={page}')
        if data['status'] not in ('ahead', 'identical'):
            raise ValueError('Release history is not a forward comparison: ' + repository)
        result.extend(data['commits'])
        if len(result) >= data['total_commits']:
            if len(result) != data['total_commits'] or len({c['sha'] for c in result}) != len(result):
                raise ValueError('Incomplete or duplicated commit comparison')
            return result
        if not data['commits']:
            raise ValueError('Truncated commit comparison')
        page += 1


def commit_notes(repository, base, head):
    changes = commits(repository, base, head)
    if not changes:
        return 'No source commit changes.\n'
    text = f'[Full comparison](https://github.com/{repository}/compare/{base}...{head})\n\n'
    for item in changes:
        sha = revision(item['sha'])
        message = item['commit']['message'].strip()
        title, _, body = message.partition('\n')
        text += f'- [`{sha[:12]}`](https://github.com/{repository}/commit/{sha}): ' + html.escape(title) + '\n'
        if body.strip():
            escaped = html.escape(body.strip()).replace('\n', '<br>')
            text += '\n  <details><summary>Commit description</summary><p>' + escaped + '</p></details>\n\n'
    return text


def release_changes(root, directory, version, info, repository):
    current = revision(info['sourceCommit'])
    engine = revision(info['engine']['sourceCommit'])
    release = api(repository, 'releases/latest', missing=True)
    if release and (release.get('draft') or release.get('prerelease')):
        raise ValueError('Expected previous stable published release')
    if release and release['tag_name'] == version:
        raise ValueError('Version already published; do not overwrite an existing release')
    previous = previous_build(repository, release) if release else None
    if previous and int(info['versionCode']) <= int(previous['versionCode']):
        raise ValueError('versionCode must increase')
    summary = curated(root, version, repository, previous['sourceCommit'] if previous else None)
    text = '## Changes in this release\n\n'
    text += summary + '\n' if summary else 'No additional curated highlights. See the commit audit below.\n'
    text += '\n## Engine changes\n\n'
    if previous:
        old = previous['engine']
        text += f"TEESimulator-RS `{old['version']}` → `{info['engine']['version']}`.\n\n"
        text += commit_notes(ENGINE_REPOSITORY, old['sourceCommit'], engine)
        text += '\n## TOPG commit audit\n\n'
        text += f"Since `{release['tag_name']}`, excluding that release's recorded commit.\n\n"
        text += commit_notes(repository, previous['sourceCommit'], current)
    else:
        text += f"Initial baseline: TEESimulator-RS `{info['engine']['version']}` (`{engine}`).\n"
        text += '\n## TOPG commit audit\n\nInitial published baseline; no previous release comparison.\n'
    text += '\nCommit descriptions are a technical audit, not a claim of device compatibility or license compliance.\n'
    return text + '\n'
