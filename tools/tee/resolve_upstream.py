#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Resolve documented TOPG integration policies; leave other conflicts intact."""
import re
import subprocess
import sys
from pathlib import Path


def git(*args):
    return subprocess.check_output(['git', *args], text=True)


def read_props(text):
    values = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or key in values:
            raise ValueError('Malformed or duplicate module property: ' + key)
        values[key] = value
    return values


def resolve(base, upstream):
    report = Path('sync-report')
    report.mkdir(exist_ok=True)
    ancestor = git('merge-base', base, upstream).strip()
    local_readme = git('show', base + ':README.md')
    remote_readme = git('show', upstream + ':README.md')
    marker = '\n## COPG-VD\n'
    if local_readme.count(marker) != 1 or not re.search(r'^# COPG-VD\s*$', remote_readme, re.M):
        raise ValueError('README structure changed; manual resolution required')
    readme = local_readme.split(marker, 1)[0] + marker + '\n' + remote_readme
    local = read_props(git('show', base + ':module/module.prop'))
    remote = read_props(git('show', upstream + ':module/module.prop'))
    old = read_props(git('show', ancestor + ':module/module.prop'))
    version = re.fullmatch(r'v(\d+)\.(\d+)(?:\.(\d+))?(?:-vd)?', remote.get('version', ''))
    if not version:
        raise ValueError('Unsupported upstream version format')
    normalized = 'v' + '.'.join(x or '0' for x in version.groups())
    if not re.fullmatch(r'v\d+\.\d+\.\d+', local.get('version', '')):
        raise ValueError('Unsupported TOPG version format')
    if tuple(map(int, normalized[1:].split('.'))) < tuple(map(int, local['version'][1:].split('.'))):
        raise ValueError('Refusing a base version downgrade')
    protected = {'id', 'name', 'author', 'support', 'description', 'updateJson'}
    if local.get('id') != 'COPG-VD' or remote.get('id') != 'COPG-VD' or local.get('name') != 'TOPG':
        raise ValueError('Unexpected module identity')
    if not local.get('versionCode', '').isdigit() or not remote.get('versionCode', '').isdigit():
        raise ValueError('Invalid versionCode')
    merged = {}
    missing = object()
    for key in dict.fromkeys([*local, *remote]):
        left, right, prior = local.get(key, missing), remote.get(key, missing), old.get(key, missing)
        if key in protected:
            value = left
        elif key == 'version':
            value = normalized
        elif key == 'versionCode':
            value = str(max(int(local[key]), int(remote[key])))
        elif left == right or right == prior:
            value = left
        elif left == prior:
            value = right
        else:
            raise ValueError('Manual module property resolution required: ' + key)
        if value is not missing:
            merged[key] = value
    (report / 'upstream-README.md').write_text(remote_readme)
    (report / 'upstream-module.prop').write_text(git('show', upstream + ':module/module.prop'))
    (report / 'upstream-workflows.txt').write_text(git('diff', '--name-status', base, upstream, '--', '.github/workflows'))
    subprocess.run(['git', 'restore', '--source=' + base, '--staged', '--worktree', '--', '.github/workflows'], check=True)
    Path('README.md').write_text(readme)
    Path('module/module.prop').write_text(''.join(k + '=' + v + '\n' for k, v in merged.items()))
    subprocess.run(['git', 'add', '--', 'README.md', 'module/module.prop'], check=True)
    (report / 'resolutions.txt').write_text('Workflows: TOPG retained; upstream CI changes require review.\nREADME: TOPG introduction/credits retained, upstream documentation refreshed.\nmodule.prop: TOPG identity/update channel retained; base version ' + normalized + '; other fields merged per key.\n')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: resolve_upstream.py BASE_SHA UPSTREAM_SHA')
    resolve(sys.argv[1], sys.argv[2])
