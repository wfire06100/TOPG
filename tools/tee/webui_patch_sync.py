#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Stage WebUI patch synchronization and early TEE startup."""
import subprocess
import sys
from pathlib import Path
from centralized_logging import configure_startup

HELPER = r'''async function teeSyncLog(message) {
    const line = String(message).replace(/[\r\n]+/g, ' ').slice(0, 2048);
    const script = `set -eu
. /data/adb/modules/COPG-VD/tee/topg_log.sh
topg_log tee_sync ${shq(line)}
`;
    try {
        await execCommand('sh -c ' + shq(script) + ' 2>&1');
    } catch (error) {
        throw new Error('TEE log unavailable: ' + String(error && error.message || error));
    }
}

async function teeSyncFailure(stage, error) {
    await teeSyncLog(stage + ' failed: ' + String(error && error.message || error));
    throw new Error('TEE sync failed at ' + stage);
}

async function syncTeeSecurityPatchFromConfig() {
    await teeSyncLog('start');
    let raw, saved;
    try {
        raw = await execCommand(`cat ${shq(CONFIG_FILE)}`);
    } catch (error) {
        const code = String(error && error.message || error).match(/error code \d+/i);
        return await teeSyncFailure('read-config', code ? code[0] : 'read failed; JSON output omitted');
    }
    try {
        saved = JSON.parse(raw);
    } catch (error) {
        return await teeSyncFailure('parse-config', 'invalid JSON');
    }
    if (!saved || typeof saved !== 'object' || Array.isArray(saved)) {
        return await teeSyncFailure('parse-config', 'expected a JSON object');
    }
    const value = (saved['COPG-VD'] || {}).SECURITY_PATCH;
    let content;
    if (value === undefined || value === null || value === '') {
        content = 'system=prop\n';
    } else {
        if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
            return await teeSyncFailure('validate-patch', 'invalid SECURITY_PATCH');
        }
        const date = new Date(value + 'T00:00:00.000Z');
        if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) {
            return await teeSyncFailure('validate-patch', 'invalid SECURITY_PATCH date');
        }
        content = `system=${value.slice(0, 7).replace('-', '')}\nboot=${value}\nvendor=${value}\n`;
    }
    const script = `set -eu
fail() { rc=$?; [ "$rc" -ne 0 ] || rc=1; printf 'step=%s rc=%s\\n' "$1" "$rc"; exit "$rc"; }
D=/data/adb/COPG-VD/tee
[ -d "$D" ] || { echo skipped-no-tee-directory; exit 0; }
umask 077
T=$(mktemp "$D/.security_patch.XXXXXX") || fail create-temp
trap 'rc=$?; rm -f "$T"; exit "$rc"' EXIT
trap 'exit 1' HUP INT TERM
printf '%s' ${shq(content)} > "$T" || fail write-temp
if [ -f "$D/security_patch.txt" ] && cmp -s "$T" "$D/security_patch.txt"; then
    echo unchanged; exit 0
fi
chmod 600 "$T" || fail chmod-temp
chcon u:object_r:adb_data_file:s0 "$T" || fail selinux-context
mv -f "$T" "$D/security_patch.txt" || fail replace-patch
echo updated
`;
    let result;
    try {
        result = await execCommand('sh -c ' + shq(script) + ' 2>&1');
    } catch (error) {
        return await teeSyncFailure('shell', error);
    }
    await teeSyncLog('completed: ' + result.trim());
    return result;
}

function reportConfigPostSaveWarning(step, error) {
    const french = (document.documentElement.lang || '').toLowerCase().startsWith('fr');
    const prefix = french ? 'JSON enregistré, mais une étape après sauvegarde a échoué' : 'JSON saved, but a post-save step failed';
    appendToOutput(prefix + ' (' + step + '): ' + String(error && error.message || error), 'warning');
}

async function syncTeeSecurityPatchAfterSave() {
    try {
        await syncTeeSecurityPatchFromConfig();
    } catch (error) {
        const french = (document.documentElement.lang || '').toLowerCase().startsWith('fr');
        const logFailed = String(error && error.message || error).startsWith('TEE log unavailable:');
        const message = logFailed
            ? (french ? 'Configuration enregistrée. Journal TEE indisponible ; synchronisation non confirmée.' : 'Configuration saved. TEE log unavailable; sync not confirmed.')
            : (french ? 'Configuration enregistrée. Échec de synchronisation TEE — consulter update.log.' : 'Configuration saved. TEE sync failed — see update.log.');
        appendToOutput(message, 'warning');
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
            const french = (document.documentElement.lang || '').toLowerCase().startsWith('fr');
            fetchStatus(french ? 'Profil récupéré ; synchronisation TEE non confirmée. Consulter update.log (ou vérifier son accès).' : 'Profile fetched; TEE sync not confirmed. See update.log (or check log access).', 'error');
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
    # Compile and stage the COPG scope helper after SDK setup, before packaging.
    root = Path(__file__).resolve().parents[2]
    subprocess.run(['bash', str(root / 'dex/build.sh')], cwd=root, check=True)
    dex = (root / 'module/etc/copgvd_scope.dex').read_bytes()
    if not dex.startswith(b'dex\n'):
        raise RuntimeError('Invalid or missing COPG scope Dex')
    target = path.parent.parent / 'etc/copgvd_scope.dex'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(dex)
    target.chmod(0o644)
    configure_startup(path.parent.parent)
    path.write_text(transform(path.read_text()))
    subprocess.run(['node', '--check', str(path)], check=True)
