#!/usr/bin/env python3
# Copyright (C) 2026 wfire06100
# SPDX-License-Identifier: Apache-2.0
"""Build-time modification notices and inventory of corresponding engine sources."""
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def notice():
    return 'TOPG modification notice: modified by wfire06100 on ' + datetime.now(timezone.utc).date().isoformat() + '; original copyright and license notices retained.'


def mark_file(path):
    raw = path.read_bytes()
    if b'\0' in raw:
        return False
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return False
    if 'TOPG modification notice:' in text:
        return True
    message = notice()
    suffix = path.suffix.lower()
    if suffix == '.json':
        data = json.loads(text)
        if not isinstance(data, dict):
            return False
        data['_TOPG_MODIFICATION_NOTICE'] = message
        result = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    elif suffix in ('.html', '.xml', '.md', '.svg'):
        comment = '<!-- ' + message + ' -->\n'
        if text.startswith('<?xml'):
            end = text.index('?>') + 2
            result = text[:end] + '\n' + comment + text[end:]
        elif text.lower().startswith('<!doctype'):
            end = text.index('>') + 1
            result = text[:end] + '\n' + comment + text[end:]
        else:
            result = comment + text
    elif suffix in ('.js', '.cjs', '.css', '.c', '.cpp', '.cc', '.h', '.hpp', '.kt', '.kts', '.java', '.rs', '.gradle'):
        comment = '/* ' + message + ' */\n'
        if text.startswith('#!'):
            first, sep, rest = text.partition('\n')
            result = first + '\n' + comment + rest
        else:
            result = comment + text
    elif text.startswith('#!') or suffix in ('.sh', '.py', '.prop', '.rule', '.yml', '.yaml', '.toml', '.properties', '.cmake') or path.name == 'CMakeLists.txt':
        comment = '# ' + message + '\n'
        if text.startswith('#!'):
            first, sep, rest = text.partition('\n')
            result = first + '\n' + comment + rest
        else:
            result = comment + text
    else:
        return False
    path.write_text(result)
    return True


def archive_sources(root, upstream, destination):
    tracked = subprocess.check_output(['git', '-C', str(upstream), 'ls-files', '--recurse-submodules', '-z']).decode().split('\0')
    tracked = sorted(filter(None, tracked))
    inventory = {}
    for name in tracked:
        path = upstream / name
        if not path.resolve().is_relative_to(upstream.resolve()):
            raise RuntimeError('Source link leaves checkout: ' + name)
        if path.is_symlink():
            import os
            inventory[name] = {'symlink': os.readlink(path)}
        elif path.is_file():
            inventory[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        else:
            raise RuntimeError('Tracked source missing; initialize all submodules: ' + name)
    changed = subprocess.check_output(['git', '-C', str(upstream), 'diff', '--name-only', 'HEAD']).decode().splitlines()
    details = notice() + '\n\nFiles differing from the selected upstream commit:\n' + ''.join('- ' + name + '\n' for name in changed)
    manifest = json.loads((upstream / 'topg-relocation.json').read_text())
    manifest['modificationNotice'] = notice()
    (upstream / 'topg-relocation.json').write_text(json.dumps(manifest, indent=2) + '\n')
    with tarfile.open(destination, 'w:gz') as archive:
        for name in tracked:
            archive.add(upstream / name, arcname='TEESimulator-RS/' + name, recursive=False)
        for name, content in [('TOPG-MODIFICATIONS.md', details), ('TOPG-SOURCE-INVENTORY.json', json.dumps(inventory, indent=2))]:
            encoded = content.encode()
            info = tarfile.TarInfo('TEESimulator-RS/' + name)
            info.size = len(encoded)
            archive.addfile(info, io.BytesIO(encoded))
        archive.add(upstream / 'topg-relocation.json', arcname='TEESimulator-RS/topg-relocation.json')
        for relative, name in [('tools/tee', 'TOPG-build-adapter'), ('module/tee', 'TOPG-runtime-adapter'), ('module/webroot/tee', 'TOPG-WebUI-adapter'), ('tests', 'TOPG-tests'), ('.github/workflows', 'TOPG-workflows')]:
            archive.add(root / relative, arcname=name)
    with tarfile.open(destination) as archive:
        for name, record in inventory.items():
            member = archive.getmember('TEESimulator-RS/' + name)
            if 'symlink' in record:
                if not member.issym() or member.linkname != record['symlink']:
                    raise RuntimeError('Source link mismatch: ' + name)
            elif hashlib.sha256(archive.extractfile(member).read()).hexdigest() != record['sha256']:
                raise RuntimeError('Source inventory mismatch: ' + name)


def mark_module(root, out):
    records = subprocess.check_output(['git', '-C', str(root), 'ls-tree', '-rz', 'HEAD', '--', 'module']).decode().split('\0')
    baseline = {}
    for record in filter(None, records):
        metadata, name = record.split('\t', 1)
        if metadata.split()[1] == 'blob':
            baseline[name.removeprefix('module/')] = metadata.split()[2]
    changes = {}
    for path in sorted(out.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        name = path.relative_to(out).as_posix()
        raw = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if name in baseline and baseline[name] != blob and path.name not in ('LICENSE', 'NOTICE'):
            marked = mark_file(path)
            if not marked:
                raise RuntimeError('Modified file needs a format-specific notice: ' + name)
            changes[name] = notice()
    # Packaging subsequently stamps the WebUI config version; preserve its notice.
    if (out / 'webroot/config.json').is_file():
        mark_file(out / 'webroot/config.json')
        changes['webroot/config.json'] = notice()
    (out / 'tee/topg-modified-files.json').write_text(json.dumps(changes, indent=2) + '\n')
    (out / 'TOPG-LICENSING.md').write_text((root / 'LICENSING.md').read_text())


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Licensing integration anchor changed: ' + old[:70])
    return text.replace(old, new, 1)


def integrate(root):
    expected = {'assemble_topg.py': '22157a60f6bc8a26ac255c37ecfd2a722ea06cb5', 'relocate_engine.py': '9a971d14651f9cb7dee48f2d9ed7a462ab15c032'}
    for name, wanted in expected.items():
        raw = (root / 'tools/tee' / name).read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if actual != wanted:
            raise RuntimeError('Licensing adapter needs review for ' + name)
    path = root / 'tools/tee/relocate_engine.py'
    relocation = path.read_text()
    relocation = replace_once(relocation, 'import argparse', 'from compliance import mark_file\nimport argparse')
    relocation = replace_once(relocation, "        path.write_bytes(updated.encode('utf-8'))", "        path.write_bytes(updated.encode('utf-8'))\n        if not mark_file(path):\n            raise RuntimeError('Engine file needs a modification notice: ' + str(path))")
    path = root / 'tools/tee/assemble_topg.py'
    assembly = replace_once(path.read_text(), 'import json', 'from compliance import mark_file, archive_sources, mark_module\nimport json')
    assembly = replace_once(assembly, ' once(p,anchor,prefix+anchor)', ' once(p,anchor,prefix+anchor)\n mark_file(p)')
    start = assembly.index(' def source_filter(info):')
    end = assembly.index(" once(out/'customize.sh'", start)
    assembly = assembly[:start] + " archive_sources(root,upstream,tee/'engine-source.tar.gz')\n" + assembly[end:]
    assembly = replace_once(assembly, " for p in out.rglob('*.sh'):", " mark_module(root,out)\n for p in out.rglob('*.sh'):")
    # Validate both generated scripts before writing either file.
    compile(relocation, 'relocate_engine.py', 'exec')
    compile(assembly, 'assemble_topg.py', 'exec')
    (root / 'tools/tee/relocate_engine.py').write_text(relocation)
    path.write_text(assembly)


def release_note():
    path = Path('release-files/RELEASE_NOTES.md')
    text = path.read_text()
    text += '\n## Corresponding source and licenses\n\nThe installable ZIP contains the modified engine and submodule sources in `tee/engine-source.tar.gz`, with `TOPG-SOURCE-INVENTORY.json` and `TOPG-MODIFICATIONS.md` inside its `TEESimulator-RS` directory. Build adapters, tests and workflows are also included. See `TOPG-LICENSING.md` in the ZIP for component licenses and source locations. The complete TOPG source and build recipe correspond to this release tag and its recorded TOPG commit.\n'
    path.write_text(text)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'release-note':
        release_note()
    else:
        integrate(Path('.').resolve())
