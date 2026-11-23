#!/usr/bin/env python3
# Copyright (C) 2026 wfire06100
# SPDX-License-Identifier: Apache-2.0
"""TOPG opt-in live VBMeta hash policy, applied before engine compilation.

Write prop to /data/adb/COPG-VD/tee/boot_hash.txt and reboot.
This only selects the hash used by the simulator; it does not set ro.boot.*.
Missing, empty, invalid or unreadable configuration retains the default policy.
An invalid live digest logs a warning and falls back to the default policy.
The saved boot_hash.bin is neither deleted nor updated by this override.
New attestations after engine restart are required; existing certificates do not change.
"""
from pathlib import Path

PREFIX = '''        // TOPG opt-in: follow live VBMeta without modifying global properties.
        if (propertyName == "ro.boot.vbmeta.digest") {
            try {
                val config = File("/data/adb/COPG-VD/tee/boot_hash.txt")
                if (config.isFile) {
                    val mode = if (config.length() <= 128L) config.readText().trim() else "invalid"
                    if (mode.equals("prop", ignoreCase = true)) {
                        val hex = SystemProperties.get(propertyName, "").orEmpty().trim()
                        if (hex.length == expectedSize * 2 && hex.all { it in "0123456789abcdefABCDEF" }) {
                            val bytes = ByteArray(expectedSize) { index ->
                                hex.substring(index * 2, index * 2 + 2).toInt(16).toByte()
                            }
                            recordSource("boot_hash.txt:prop")
                            SystemLogger.debug("TOPG boot hash source: live VBMeta (boot_hash.txt=prop)")
                            return bytes
                        }
                        SystemLogger.info("TOPG boot_hash.txt=prop: invalid VBMeta digest; using default policy")
                    } else if (mode.isNotEmpty()) {
                        SystemLogger.info("TOPG boot_hash.txt: unsupported mode; using default policy")
                    }
                }
            } catch (e: Exception) {
                SystemLogger.error("TOPG failed to read boot_hash.txt; using default policy", e)
            }
        }
'''


def apply(upstream):
    path = Path(upstream) / 'app/src/main/java/org/matrix/TEESimulator/util/AndroidDeviceUtils.kt'
    text = path.read_text()
    anchor = '        // TOPG: preserve existing boot identity before consulting live properties.\n'
    if 'boot_hash.txt:prop' in text:
        raise RuntimeError('Boot hash policy already patched')
    if text.count(anchor) != 1:
        raise RuntimeError('TOPG persistent boot identity anchor changed')
    path.write_text(text.replace(anchor, PREFIX + anchor, 1))
