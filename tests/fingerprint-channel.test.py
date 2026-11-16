#!/usr/bin/env python3
"""Run isolated updater regressions without Android or network access."""
import os
import subprocess
import tempfile
from pathlib import Path

source = Path('module/fingerprint-update.sh').read_text()
def function(name, following):
    start = source.index(name + '() {')
    return source[start:source.index(following + '() {', start)]

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    config = root / 'config.json'
    config.write_text('{}')
    setup = 'CONFIG_PATHS=' + str(config) + '\n' + '''json_get() {
 case "$2" in
 FINGERPRINT) printf '%s\n' "$TEST_FP";;
 PREVIEW_SDK) printf '%s\n' "$TEST_PREVIEW";;
 esac
}
'''
    cases = [
        ('google/bluejay_beta/bluejay:CANARY/ZP11.261016.008/16754936:user/release-keys', '1', 'canary'),
        ('google/bluejay_beta/bluejay:canary/X/1:user/release-keys', '0', 'canary'),
        ('google/bluejay_beta/bluejay:17/DP11.261030.003/16847878:user/release-keys', '1', 'beta'),
        ('google/bluejay/bluejay:17/X/1:user/release-keys', '0', 'release'),
        ('google/bluejay/bluejay:17/X/1:user/release-keys', '1', None),
        ('invalid', '0', None),
    ]
    for fingerprint, preview, expected in cases:
        result = subprocess.run(['sh'], input=setup + function('detect_channel_from_fingerprint', 'update_non_tegu_profile') + '\ndetect_channel_from_fingerprint\n', text=True, capture_output=True, env={**os.environ, 'TEST_FP': fingerprint, 'TEST_PREVIEW': preview})
        if expected is None:
            assert result.returncode != 0 and not result.stdout, (fingerprint, result)
        else:
            assert result.returncode == 0 and result.stdout.strip() == expected, (fingerprint, result)
    apply = function('apply_profile', 'spoofed_device')
    driver = root / 'driver.sh'
    for child_status, child_rc, expected in [('fetched', 0, 'applied'), ('failed', 1, 'failed'), ('unexpected', 0, 'failed')]:
        driver.write_text('''#!/bin/sh
if [ "${1:-}" = fetch ]; then
 echo '[COPG-VD] test fetch message'
 printf 'status: %s\n' "$TEST_STATUS"
 exit "$TEST_RC"
fi
log() { printf '[COPG-VD] %s\n' "$*"; }
cfg_setting() { echo false; }
KILL_PACKAGES=''
''' + apply + '''
if apply_profile bluejay/test.prop; then echo 'status: applied'; else echo 'status: failed'; fi
''')
        result = subprocess.run(['sh', str(driver)], text=True, capture_output=True, env={**os.environ, 'TEST_STATUS': child_status, 'TEST_RC': str(child_rc)})
        statuses = [line for line in result.stdout.splitlines() if line.startswith('status:')]
        assert statuses == ['status: ' + expected], (child_status, result.stdout, result.stderr)
        assert '[COPG-VD] test fetch message' in result.stdout
print('Passed six channel fixtures and three final-status fixtures')
