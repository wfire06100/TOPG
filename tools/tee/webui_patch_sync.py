#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Stage WebUI patch synchronization and early TEE startup."""
import subprocess
import sys
from pathlib import Path
from startup_patch import configure_startup

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
fail() { printf 'status: tee-patch-sync-failed: %s\n' "$1"; exit 1; }
D=/data/adb/COPG-VD/tee
[ -d "$D" ] || exit 0
umask 077
T=$(mktemp "$D/.security_patch.XXXXXX") || fail create-temp
trap 'rc=$?; rm -f "$T"; exit "$rc"' EXIT
trap 'exit 1' HUP INT TERM
printf '%s' ${shq(content)} > "$T" || fail write-temp
if [ -f "$D/security_patch.txt" ] && cmp -s "$T" "$D/security_patch.txt"; then
    exit 0
fi
chmod 600 "$T" || fail chmod-temp
chcon u:object_r:adb_data_file:s0 "$T" || fail selinux-context
mv -f "$T" "$D/security_patch.txt" || fail replace-patch
`);
}

function reportConfigPostSaveWarning(step, error) {
    const french = (document.documentElement.lang || '').toLowerCase().startsWith('fr');
    const prefix = french ? 'JSON enregistré, mais une étape après sauvegarde a échoué' : 'JSON saved, but a post-save step failed';
    appendToOutput(prefix + ' (' + step + '): ' + String(error.message || error), 'warning');
}

async function syncTeeSecurityPatchAfterSave() {
    try {
        await syncTeeSecurityPatchFromConfig();
    } catch (error) {
        reportConfigPostSaveWarning('TEE sync', error);
    }
}

'''


def transform(source):
    replacements = [
        ('async function saveConfig() {', HELPER + 'async function saveConfig() {'),
        ('        await execCommand(`chmod 644 ${shq(CONFIG_FILE)}`);',
         '        await execCommand(`chmod 644 ${shq(CONFIG_FILE)}`);\n'
         '        await syncTeeSecurityPatchAfterSave();'),
        ('        await execCommand(`kill -9 $(pidof com.android.vending com.google.android.gsf com.google.android.gms) 2>/dev/null`);',
         """        try {
            await execCommand(`pids=$(pidof com.android.vending com.google.android.gsf com.google.android.gms 2>/dev/null || :)
if [ -n "$pids" ]; then kill -9 $pids; fi`);
        } catch (error) {
            reportConfigPostSaveWarning('Play services restart', error);
        }"""),
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
    configure_startup(path.parent.parent)
    path.write_text(transform(path.read_text()))
    subprocess.run(['node', '--check', str(path)], check=True)
