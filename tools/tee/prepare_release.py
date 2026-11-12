#!/usr/bin/env python3
# Copyright (C) 2026 wfire06100
# SPDX-License-Identifier: Apache-2.0
'Verify the current build and prepare notes without changing its version suffix.'
import hashlib
import json
import os
import re
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

Intégration de COPG-VD et TEESimulator-RS maintenue par wfire06100.

## Fonctionnalités

- Onglet TEE et ciblage des applications en modes Auto, Generate (`!`) ou Hack (`?`).
- Import de keybox personnelle et téléchargements XML/base64 planifiés.
- Migration ou initialisation des données avec sauvegardes et conservation des clés persistantes.
- Contrôleur de navigation commun aux six onglets et verrouillage portable des opérations TEE.

## Installation et limites

Télécharger `{archive_path.name}`, pas les archives de code source GitHub. Sauvegarder les données, suivre les instructions de l'installateur et redémarrer. Android 10 ou plus récent est requis par cette intégration.

Les tests automatisés et contrôles du ZIP ne certifient pas la compatibilité sur appareil réel. Aucun résultat Play Integrity ou Wallet n'est garanti. Une vérification de structure de keybox ne prouve ni sa validité cryptographique ni sa non-révocation. Le miroir HTTP par défaut n'est pas authentifié.

## Informations du build

- Version complète : `{version}` (suffixe conservé).
- Version code : `{props['versionCode']}`.
- Commit TOPG : `{source}`.
- Moteur : TEESimulator-RS `{info['engine']['version']}`.
- Commit moteur : `{info['engine']['sourceCommit']}`.
- SHA-256 : `{digest}`.

## Crédits et licences

TOPG : wfire06100. COPG/COPG-VD : AlirezaParsi et VD171. TEESimulator original : JingMatrix. TEESimulator-RS : Enginex0 et les contributeurs. Les licences Apache-2.0 et GPL-3.0 et les notices des composants sont conservées.
'''
    photos = sorted(p for p in (root / 'screenshots/topg').glob('*')
                    if p.is_file() and p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'))
    title = 'Captures TOPG'
    if not photos:
        title = 'Captures de la base COPG-VD'
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
    archive, checksum, notes = prepare(Path('.').resolve(), Path('release-files').resolve(),
        os.environ['VERSION'], os.environ['EXPECTED_SHA256'], os.environ['GITHUB_SHA'], os.environ['GITHUB_REPOSITORY'])
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write(f'zip={archive}\nchecksum={checksum}\nnotes={notes}\n')
