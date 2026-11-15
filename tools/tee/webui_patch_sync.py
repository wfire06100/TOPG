#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply TOPG patch-level synchronization to the staged WebUI."""
import subprocess
import sys
from pathlib import Path

HELPER = r'''async function syncTeeSecurityPatchFromConfig() {
    const saved = JSON.parse(await execCommand(`cat ${shq(CONFIG_FILE)}`));
    const value = (saved['COPG-VD'] || {}).SECURITY_PATCH;
    let content;
    if (value === undefined || value === null || value === '') {
        content = 'system=prop\n';
    } else {
        if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
            throw new Error('TEE: invalid SECURITY_PATCH; previous configuration preserved');
        }
        const date = new Date(value + 'T00:00:00.000Z');
        if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) {
            throw new Error('TEE: invalid SECURITY_PATCH date; previous configuration preserved');
        }
        content = `system=${value.slice(0, 7).replace('-', '')}\nboot=${value}\nvendor=${value}\n`;
    }
    return await execCommand(`set -eu
D=/data/adb/COPG-VD/tee
[ -d "$D" ] || exit 0
umask 077
T=$(mktemp "$D/.security_patch.XXXXXX")
trap 'rm -f "$T"' EXIT HUP INT TERM
printf '%s' ${shq(content)} > "$T"
if [ -f "$D/security_patch.txt" ] && cmp -s "$T" "$D/security_patch.txt"; then
    exit 0
fi
chmod 600 "$T"
chcon u:object_r:adb_data_file:s0 "$T"
mv -f "$T" "$D/security_patch.txt"
`);
}

'''


def transform(source):
    replacements = [
        ('async function saveConfig() {', HELPER + 'async function saveConfig() {'),
        ('        await execCommand(`chmod 644 ${shq(CONFIG_FILE)}`);',
         '        await execCommand(`chmod 644 ${shq(CONFIG_FILE)}`);\n'
         '        await syncTeeSecurityPatchFromConfig();'),
        ("    if (status === 'fetched') {\n        await loadConfig();",
         """    if (status === 'fetched') {
        try {
            await syncTeeSecurityPatchFromConfig();
        } catch (error) {
            await loadConfig();
            renderDeviceList();
            fillIdentityPlate();
            fetchStatus(t('msg_fetch_fail', {"error": String(error)}), 'error');
            return;
        }
        await loadConfig();"""),
    ]
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError('WebUI synchronization anchor changed: ' + old)
        source = source.replace(old, new, 1)
    return source


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: webui_patch_sync.py SCRIPTS_JS')
    path = Path(sys.argv[1])
    path.write_text(transform(path.read_text()))
    subprocess.run(['node', '--check', str(path)], check=True)
