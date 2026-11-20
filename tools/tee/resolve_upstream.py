#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Resolve explicit TOPG policies; refuse unreviewed integration changes."""
import re
import subprocess
import sys
from pathlib import Path

COPG_616 = '9a40e885c8c00905998ab24a52239e3cf6ea8633'


def git(*args):
    return subprocess.check_output(['git', *args], text=True)


def run(*args):
    subprocess.run(['git', *args], check=True)


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


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Reviewed integration anchor changed: ' + old[:100])
    return text.replace(old, new, 1)


def function(text, name):
    pattern = r'^async function ' + re.escape(name) + r'\([^\n]*\) \{.*?^\}'
    matches = list(re.finditer(pattern, text, re.M | re.S))
    if len(matches) != 1:
        raise ValueError('Function boundary changed: ' + name)
    return matches[0].group()


def resolve_616(base, upstream, ancestor):
    if upstream != COPG_616:
        raise ValueError('Functional integration policy reviewed only for COPG 6.16 commit ' + COPG_616)
    read = lambda rev, path: git('show', rev + ':' + path)
    js_path = 'module/webroot/scripts.js'
    local, remote, prior = (read(rev, js_path) for rev in (base, upstream, ancestor))
    result = local
    for name in ('openAppPicker', 'backupFile', 'restoreFile'):
        original = function(prior, name)
        current = function(local, name)
        if current != original:
            raise ValueError('TOPG changed ' + name + '; manual semantic review required')
        replacement = function(remote, name)
        if name == 'openAppPicker':
            start = remote.index('const DEX_ENV_PREFIX =')
            stop = remote.index(replacement)
            if stop <= start:
                raise ValueError('Scope helper boundaries changed')
            replacement = remote[start:stop] + replacement
            for symbol in ('const DEX_ENV_PREFIX =', 'async function enumerateScopeTargets('):
                if symbol in local:
                    raise ValueError('Scope helper already customized')
        result = once(result, current, replacement)
    result = once(result, 'in: "Bahasa Indonesia"', 'id: "Bahasa Indonesia"')
    if 'loadVdluI18n' in result or re.search(r'\bVDLU\.', result):
        raise ValueError('TOPG source still contains active VDLU code; review required')
    css_path = 'module/webroot/styles.css'
    css_local, css_remote, css_prior = (read(rev, css_path) for rev in (base, upstream, ancestor))
    def scope_css(text):
        start = text.index('.scope-app-filter {')
        end = text.index('.scope-apps-save, .scope-apps-cancel', start)
        if '.scope-app-search {' in text[:start]:
            raise ValueError('Scope CSS already changed')
        return text[start:end]
    old_css = scope_css(css_prior)
    if scope_css(css_local) != old_css:
        raise ValueError('TOPG scope CSS changed; manual review required')
    start = css_remote.index('.scope-app-search {')
    end = css_remote.index('.scope-apps-save, .scope-apps-cancel', start)
    css = once(css_local, old_css, css_remote[start:end])
    workflow_path = '.github/workflows/COPG-VD.yml'
    workflow = Path(workflow_path).read_text()
    anchor = '      - name: Build COPG libraries\n'
    step = "      - name: Build COPG scope helper\n        if: steps.built.outputs.cache-hit != 'true'\n        run: |\n          bash dex/build.sh\n          test -s module/etc/copgvd_scope.dex\n"
    workflow = once(workflow, anchor, step + anchor)
    paths = git('ls-files', '-z').split('\0')
    vdlu = sorted(set(p for p in paths if p.startswith(('module/vdlu/', 'module/webroot/vdlu-i18n/')) or p in ('module/webroot/vdlu.js', 'module/webroot/vdlu.css')))
    if vdlu:
        run('rm', '-f', '--ignore-unmatch', '--', *vdlu)
    Path(js_path).write_text(result)
    Path(css_path).write_text(css)
    Path(workflow_path).write_text(workflow)
    updater = 'module/fingerprint-update.sh'
    run('restore', '--source=' + base, '--staged', '--worktree', '--', updater)
    subprocess.run(['node', '--check', js_path], check=True)
    subprocess.run(['sh', '-n', updater], check=True)
    run('add', '--', js_path, css_path, workflow_path)
    with (Path('sync-report') / 'resolutions.txt').open('a') as out:
        out.write('COPG 6.16: scope picker/helpers and CSS ported to TOPG; Backup/Restore corrected; Indonesian language code updated.\n')
        out.write('TOPG fingerprint updater retained byte-for-byte from base. VDLU files removed, including newly added translations.\n')
        out.write('TOPG build workflow retained with explicit Dex compilation. Other conflicts remain blocking.\n')


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
    run('restore', '--source=' + base, '--staged', '--worktree', '--', '.github/workflows')
    Path('README.md').write_text(readme)
    Path('module/module.prop').write_text(''.join(k + '=' + v + '\n' for k, v in merged.items()))
    run('add', '--', 'README.md', 'module/module.prop')
    (report / 'resolutions.txt').write_text('Workflows: TOPG retained; upstream CI changes require review.\nREADME: TOPG introduction/credits retained, upstream documentation refreshed.\nmodule.prop: TOPG identity/update channel retained; base version ' + normalized + '; other fields merged per key.\n')
    resolve_616(base, upstream, ancestor)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: resolve_upstream.py BASE_SHA UPSTREAM_SHA')
    resolve(sys.argv[1], sys.argv[2])
