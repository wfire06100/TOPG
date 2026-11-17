#!/usr/bin/env python3
# Copyright (C) 2026 wfire06100
# SPDX-License-Identifier: Apache-2.0
"""Integrate TEE into the reviewed shared tab controller."""
import hashlib
import re
import sys
from pathlib import Path

SWITCH = r'''function switchTab(tabId, direction = null) {
    const tabs = ['about', 'devices', 'spoofing', 'system', 'tools', 'tee'];
    if (!tabs.includes(tabId)) return;
    const next = document.getElementById(`${tabId}-tab`);
    if (!next) return;
    const current = currentTabId();
    if (current === tabId && next.classList.contains('active')) return;
    if (switchTab.pendingFrame != null) cancelAnimationFrame(switchTab.pendingFrame);
    switchTab.pendingFrame = null;
    activeOutput = null;

    for (const id of tabs) {
        const selected = id === tabId;
        const panel = document.getElementById(`${id}-tab`);
        if (panel) {
            panel.classList.toggle('active', selected);
            panel.style.display = selected ? 'block' : 'none';
            panel.style.transition = 'none';
            panel.style.transform = 'translateX(0)';
            panel.style.opacity = '0';
        }
        document.getElementById(`tab-${id}`)?.classList.toggle('active', selected);
    }
    const inferred = direction || (tabs.indexOf(tabId) > tabs.indexOf(current) ? 'left' : 'right');
    next.style.transform = inferred === 'left' ? 'translateX(100%)' : 'translateX(-100%)';
    void next.offsetHeight;
    switchTab.pendingFrame = requestAnimationFrame(() => {
        switchTab.pendingFrame = null;
        if (!next.classList.contains('active')) return;
        next.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
        next.style.transform = 'translateX(0)';
        next.style.opacity = '1';
        if (tabId === 'devices') setTimeout(() => renderDeviceList(), 100);
        if (tabId === 'tools') checkRebootPending();
    });
    const sb = document.getElementById('device-savebar');
    if (sb) sb.style.display = tabId === 'devices' ? '' : 'none';
    if (!navFromPop) { try { history.pushState({ tab: tabId }, ''); } catch (e) {} }
}'''

REVIEWED = {
    '7fb5f3bb1e8ad2afaebef05c078fe0726e1e43cbff5242a38b817a5a139e0ed3':
        "const tabs = ['about', 'devices', 'spoofing', 'system', 'tools'];",
}


def apply(root):
    script = root / 'module/webroot/scripts.js'
    tee = root / 'module/webroot/tee/tee.js'
    source = script.read_text()
    match = re.search(r'^function switchTab\(tabId, direction = null\) \{.*?^\}', source, re.M | re.S)
    digest = hashlib.sha256(match.group().encode()).hexdigest() if match else None
    old_tabs = REVIEWED.get(digest)
    if old_tabs is None:
        raise RuntimeError('Shared navigation controller changed; review required')
    if source.count(old_tabs) != 2:
        raise RuntimeError('Navigation tab lists changed')
    new_tabs = old_tabs[:-2] + ", 'tee'];"
    replacement = SWITCH.replace("const tabs = ['about', 'devices', 'spoofing', 'system', 'tools', 'tee'];", new_tabs, 1)
    source = source[:match.start()] + replacement + source[match.end():]
    source = source.replace(old_tabs, new_tabs, 1)
    content = tee.read_text()
    handler = r"^ btn.addEventListener\('click',e=>\{e.stopImmediatePropagation\(\);.*?act\(status\);\},true\);$"
    matches = list(re.finditer(handler, content, re.M))
    if len(matches) != 1:
        raise RuntimeError('TEE click handler changed')
    content = re.sub(handler, " btn.addEventListener('click',()=>{switchTab('tee');act(status);});", content, count=1, flags=re.M)
    script.write_text(source)
    tee.write_text(content)
    from about_popup import apply as apply_about_popup
    apply_about_popup(root)


if __name__ == '__main__':
    apply(Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve())
