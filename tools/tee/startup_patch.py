#!/usr/bin/env python3
# Copyright (C) 2026 wfire06100
# SPDX-License-Identifier: Apache-2.0
"""Stage early TEE startup with a one-second delay and bounded retries."""
import subprocess
from pathlib import Path

WORKER = r'''#!/system/bin/sh
# Copyright (C) 2026 wfire06100; SPDX-License-Identifier: Apache-2.0
set -u
umask 077
M=${0%/*}
D=/data/adb/COPG-VD/tee
cd "$M" || exit 1
sleep 1
attempt=1
while [ "$attempt" -le 30 ]; do
 [ ! -e "$M/../disable" ] && [ ! -e "$M/../remove" ] || exit 0
 echo "TEE startup attempt=$attempt uptime=$(cut -d' ' -f1 /proc/uptime)"
 if ./supervisor ./daemon "$M"; then rc=0; else rc=$?; fi
 echo "TEE supervisor exited rc=$rc attempt=$attempt"
 [ "$attempt" -lt 30 ] || break
 attempt=$((attempt + 1))
 sleep 1
done
echo 'TEE startup retries exhausted; a later boot command may retry.'
exit 1
'''


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError('TEE startup anchor changed: ' + old)
    return source.replace(old, new, 1)


def configure_startup(module):
    module = Path(module)
    manager = module / 'tee/tee_manager.sh'
    service = module / 'service.sh'
    text = manager.read_text()
    text = replace_once(text,
        ' [ "$(cat "$D/boot.id" 2>/dev/null || true)" != "$bootid" ] || exit 0',
        r''' if [ "$(cat "$D/boot.id" 2>/dev/null || true)" = "$bootid" ]; then
  pid=$(cat "$D/engine.pid" 2>/dev/null || true)
  case "$pid" in ''|*[!0-9]*) ;; *)
   if kill -0 "$pid" 2>/dev/null && tr '\000' ' ' < "/proc/$pid/cmdline" | grep -F -q "$M"; then
    exit 0
   fi ;;
  esac
 fi''')
    text = replace_once(text,
        ' (exec 9>&-; cd "$M"; sleep 30; exec ./supervisor ./daemon "$M") >> "$D/runtime.log" 2>&1 &',
        ' (exec 9>&-; exec sh "$M/tee_start.sh") >> "$D/runtime.log" 2>&1 &')
    service_text = replace_once(service.read_text(),
        'until [ "$(getprop sys.boot_completed)" = "1" ]; do',
        'sh "$MODDIR/tee/tee_manager.sh" boot >> "$DATA_DIR/tee-boot.log" 2>&1\n\nuntil [ "$(getprop sys.boot_completed)" = "1" ]; do')
    for name, content in [('manager', text), ('service', service_text), ('worker', WORKER)]:
        subprocess.run(['sh', '-n'], input=content, text=True, check=True)
    manager.write_text(text)
    service.write_text(service_text)
    (module / 'tee/tee_start.sh').write_text(WORKER)

