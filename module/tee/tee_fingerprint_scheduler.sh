#!/system/bin/sh
# Copyright (C) 2026 wfire06100; SPDX-License-Identifier: Apache-2.0
set -eu
umask 077
M=${0%/*}
D=/data/adb/COPG-VD/tee
mkdir -p "$D"
cmd=${1:-status}
. "$M/tee_lock.sh"
if [ "$cmd" = run ]; then
 tee_lock_acquire "$D/.fingerprint-daemon.lock" 0 || exit 0
 while [ ! -e "$M/../disable" ] && [ ! -e "$M/../remove" ]; do
  sh "$0" tick >> "$D/fingerprint.log" 2>&1 || true
  sleep 10
 done
 exit 0
fi
tee_lock_acquire "$D/.fingerprint-operation.lock" 3 || exit "$?"
load() {
 minutes=0; due=0
 if [ -f "$D/fingerprint.schedule" ]; then read -r minutes due < "$D/fingerprint.schedule" || true; fi
 case "$minutes" in ''|*[!0-9]*) minutes=0;; esac
 case "$due" in ''|*[!0-9]*) due=0;; esac
 [ "$minutes" -le 10080 ] || minutes=0
}
save() {
 tmp=$(mktemp "$D/.fingerprint-schedule.XXXXXX")
 printf '%s %s\n' "$minutes" "$due" > "$tmp"
 mv -f "$tmp" "$D/fingerprint.schedule"
}
update_fingerprint() {
 before=$(cksum "${D%/tee}/COPG-VD.json" 2>/dev/null || true)
 if sh "$M/../fingerprint-update.sh" "$1"; then update_rc=0; else update_rc=$?; fi
 after=$(cksum "${D%/tee}/COPG-VD.json" 2>/dev/null || true)
 if [ "$before" != "$after" ]; then
  if ! sh "$M/../service.sh" --props-only; then
   echo 'status: tee-sync-failed' >&2
   return 1
  fi
 fi
 return "$update_rc"
}
load
case "$cmd" in
status)
 printf 'minutes=%s\nnext=%s\n' "$minutes" "$due"
 cat "$D/fingerprint.result" 2>/dev/null || true ;;
configure)
 minutes=${2:-}
 case "$minutes" in ''|*[!0-9]*|0[0-9]*) echo invalid_interval >&2; exit 1;; esac
 [ "${#minutes}" -le 5 ] && [ "$minutes" -le 10080 ] || { echo invalid_interval >&2; exit 1; }
 due=0; [ "$minutes" -eq 0 ] || due=$(( $(date +%s) + minutes * 60 ))
 save ;;
check|apply)
 update_fingerprint "$cmd" ;;
tick)
 [ "$minutes" -gt 0 ] || exit 0
 [ "$(getprop sys.boot_completed)" = 1 ] || exit 0
 now=$(date +%s)
 if [ "$due" -gt "$((now + minutes * 60))" ] || [ "$due" -eq 0 ]; then due=$((now + minutes * 60)); save; fi
 [ "$now" -ge "$due" ] || exit 0
 due=$((now + minutes * 60)); save
 if update_fingerprint apply; then rc=0; else rc=$?; fi
 tmp=$(mktemp "$D/.fingerprint-result.XXXXXX")
 printf 'last=%s\nresult=%s\n' "$now" "$rc" > "$tmp"
 mv -f "$tmp" "$D/fingerprint.result" ;;
*) exit 1 ;;
esac
