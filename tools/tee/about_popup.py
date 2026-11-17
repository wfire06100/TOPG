#!/usr/bin/env python3
# Copyright (C) 2026 wfire06100
# SPDX-License-Identifier: Apache-2.0
"""Move the existing About markup into a dialog without rewriting its credits."""
import re
import subprocess
from pathlib import Path

CSS = '''
/* TOPG About: reuse the existing About cards and theme. */
#tab-about.topg-about-button {
 min-width: 0; flex: none; padding: 8px 12px; height: 38px;
 border-radius: var(--r-ctrl); white-space: nowrap;
}
#topg-about-dialog {
 position: fixed; inset: 0; margin: auto; padding: 0;
 width: calc(100% - 32px); max-width: 560px; max-height: 88vh;
 color: var(--ink); background: var(--surface);
 border: 1px solid var(--line); border-radius: var(--r-card);
 box-shadow: var(--shadow-pop); font-family: var(--sans);
}
#topg-about-dialog:not([open]) { display: none; }
#topg-about-dialog[open] { display: flex; flex-direction: column; }
#topg-about-dialog::backdrop { background: var(--overlay); backdrop-filter: blur(3px); }
#topg-about-dialog .topg-about-body {
 padding: 14px 20px; overflow-y: auto; overscroll-behavior: contain; min-height: 0;
}
#topg-about-dialog .about-val { overflow-wrap: anywhere; }
@media (max-width: 380px) { .header { flex-wrap: wrap; } .header-actions { margin-left: auto; } }
'''

JS = '''
/* Copyright (C) 2026 wfire06100; SPDX-License-Identifier: Apache-2.0 */
(() => {
 'use strict';
 function setup() {
  const button = document.getElementById('tab-about');
  const dialog = document.getElementById('topg-about-dialog');
  if (!button || !dialog) return;
  const close = dialog.querySelector('[data-topg-about-close]');
  let overflow = '';
  button.addEventListener('click', () => {
   if (dialog.open) return;
   overflow = document.body.style.overflow;
   dialog.showModal();
   document.body.style.overflow = 'hidden';
   button.setAttribute('aria-expanded', 'true');
  });
  close.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
   document.body.style.overflow = overflow;
   button.setAttribute('aria-expanded', 'false');
   button.focus();
  });
  dialog.addEventListener('click', event => {
   if (event.target !== dialog) return;
   const r = dialog.getBoundingClientRect();
   if (event.clientX < r.left || event.clientX > r.right ||
       event.clientY < r.top || event.clientY > r.bottom) dialog.close();
  });
  for (const name of ['touchstart', 'touchmove', 'touchend'])
   dialog.addEventListener(name, event => event.stopPropagation(), {passive: true});
 }
 if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup, {once: true});
 else setup();
})();
'''


def apply(root):
    web = Path(root) / 'module/webroot'
    path = web / 'index.html'
    text = path.read_text()
    start = '<div id="about-tab" class="tab-content active">'
    end = '<div id="devices-tab" class="tab-content">'
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError('About or Device markup changed; review required')
    before, rest = text.split(start, 1)
    about, after = rest.split(end, 1)
    body, closing = about.rsplit('</div>', 1)
    if closing.strip():
        raise RuntimeError('Unexpected About closing markup')
    project = re.search(r'<div class="about-sec" data-i18n="ui_about_sec_project">Project</div>.*?(?=<div class="about-sec")', body, re.S)
    if project is None:
        raise RuntimeError('Project credits changed; review required')
    credit = project.group()
    credit = credit.replace(' data-i18n="ui_about_sec_project"', '').replace('>Project</div>', '>Topg Project</div>', 1)
    credit = credit.replace('github.com/VD171/COPG-VD', 'github.com/wfire06100/TOPG')
    credit = credit.replace('github.com/VD171', 'github.com/wfire06100')
    credit = credit.replace('fork by VD171', 'fork by wfire06100')
    credit = credit.replace('Apache License 2.0', 'Apache License 2.0<br>GNU General Public License v3.0')
    body = body[:project.start()] + credit + body[project.start():]
    text = before + '<div id="devices-tab" class="tab-content active">' + after
    old = '<button id="tab-about" class="tab-btn active" data-i18n="ui_tab_about">About</button>'
    if text.count(old) != 1:
        raise RuntimeError('About navigation button changed')
    text = text.replace(old, '', 1)
    anchor = '<button id="lang-toggle"'
    if text.count(anchor) != 1:
        raise RuntimeError('Language button changed')
    button = '<button type="button" id="tab-about" class="action-btn topg-about-button" aria-haspopup="dialog" aria-controls="topg-about-dialog" aria-expanded="false">About</button>\n                '
    text = text.replace(anchor, button + anchor, 1)
    text = text.replace('<button id="tab-devices" class="tab-btn"', '<button id="tab-devices" class="tab-btn active"', 1)
    dialog = '<dialog id="topg-about-dialog" aria-labelledby="topg-about-title"><div class="modal-header"><h3 id="topg-about-title">About</h3></div><div class="topg-about-body">' + body + '</div><div class="popup-footer"><button type="button" class="cancel-btn" data-topg-about-close data-i18n="ui_009" autofocus>Close</button></div></dialog>\n<script src="tee/about_popup.js" defer></script>\n'
    if text.count('</body>') != 1 or text.count('</head>') != 1:
        raise RuntimeError('HTML document anchors changed')
    text = text.replace('</body>', dialog + '</body>', 1)
    text = text.replace('</head>', '<link rel="stylesheet" href="tee/about_popup.css">\n</head>', 1)
    script = web / 'tee/about_popup.js'
    script.write_text(JS)
    subprocess.run(['node', '--check', str(script)], check=True)
    (web / 'tee/about_popup.css').write_text(CSS)
    path.write_text(text)
