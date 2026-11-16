"""Stage shared tagged logging without changing WebUI command output."""
import subprocess
from pathlib import Path
from startup_patch import configure_startup as original_startup

LOGGER = r'''#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Source only; keep stdout available for the WebUI protocol.
topg_log() (
 umask 077
 tag=$1; shift
 case "$tag" in tee_sync|fingerprint|keybox) ;; *) return 2;; esac
 P=/data/adb/COPG-VD
 mkdir -p "$P" || return 1
 L=$P/update.log
 lock=$P/.update-log.lock
 n=0
 until mkdir "$lock" 2>/dev/null; do
  n=$((n+1)); [ "$n" -lt 5 ] || return 1
  sleep 1
 done
 trap 'rmdir "$lock" 2>/dev/null || :' EXIT
 if [ -f "$L" ] && [ "$(wc -c < "$L")" -gt 32768 ]; then
  R=$(mktemp "$P/.update-log.XXXXXX") || return 1
  tail -c 8192 "$L" > "$R" && cat "$R" > "$L"
  rm -f "$R"
 fi
 message=$(printf '%s' "$*" | tr '\r\n' '  ' | cut -c 1-2048)
 printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$tag" "$message" >> "$L" || return 1
 chmod 600 "$L"
)
'''

def once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Central logging anchor changed: ' + old[:100])
    return text.replace(old, new, 1)

def configure_startup(module):
    original_startup(module)
    module = Path(module)
    updates = {}
    updater = module / 'fingerprint-update.sh'
    text = updater.read_text()
    begin = text.index('log() {\n')
    end = text.index('\ncleanup() {', begin)
    text = text[:begin] + '''. "$MODDIR/tee/topg_log.sh"
log() {
    echo "[$MODULE_ID] $*"
    topg_log fingerprint "$*" || :
}
''' + text[end:]
    updates[updater] = text
    scheduler = module / 'tee/tee_fingerprint_scheduler.sh'
    text = once(scheduler.read_text(), 'M=${0%/*}\n', 'M=${0%/*}\n. "$M/topg_log.sh"\n')
    text = once(text, '  sh "$0" tick >> "$D/fingerprint.log" 2>&1 || true', '  if sh "$0" tick >/dev/null 2>&1; then :; else\n   rc=$?; topg_log fingerprint "scheduled operation failed rc=$rc" || :\n  fi')
    text = once(text, "   echo 'status: tee-sync-failed' >&2", "   topg_log tee_sync 'fingerprint props synchronization failed' || :\n   echo 'status: tee-sync-failed' >&2")
    text = once(text, ' due=0; [ "$minutes" -eq 0 ]', ' topg_log fingerprint "schedule configured minutes=$minutes" || :\n due=0; [ "$minutes" -eq 0 ]')
    updates[scheduler] = text
    worker = module / 'tee/tee_start.sh'
    updates[worker] = once(worker.read_text(), 'sh "$M/tee_fingerprint_scheduler.sh" run >> "$D/fingerprint.log" 2>&1 &', 'sh "$M/tee_fingerprint_scheduler.sh" run >/dev/null 2>&1 &')
    keybox = module / 'tee/tee_keybox.sh'
    text = once(keybox.read_text(), 'DEFAULT_URL=http://evoker.qzz.io/key\n', '''DEFAULT_URL=http://evoker.qzz.io/key
. "${0%/*}/topg_log.sh"
keybox_exit() {
 rc=$?
 trap - EXIT
 [ -z "${T:-}" ] || rm -rf "$T"
 if [ "$rc" -ne 0 ]; then topg_log keybox "operation failed rc=$rc" || :; fi
 exit "$rc"
}
trap 'keybox_exit' EXIT
''')
    text = once(text, "trap 'rm -rf \"$T\"' EXIT HUP INT TERM".replace('\\"', '"'), "trap 'exit 1' HUP INT TERM")
    for result in ('settings_saved', 'imported', 'unchanged', 'updated'):
        text = once(text, 'echo ' + result, 'topg_log keybox ' + result + ' || :; echo ' + result)
    text = once(text, 'rc=$?; echo "download: $engine failed (exit $rc)"', 'rc=$?; topg_log keybox "download method=$engine failed rc=$rc" || :; echo "download: $engine failed (exit $rc)"')
    updates[keybox] = text
    updates[module / 'tee/topg_log.sh'] = LOGGER
    for path, content in updates.items():
        subprocess.run(['sh', '-n'], input=content, text=True, check=True)
    for path, content in updates.items():
        path.write_text(content)
