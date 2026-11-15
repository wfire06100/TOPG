#!/usr/bin/env python3
# Copyright (C) 2026 wfire06100
# SPDX-License-Identifier: Apache-2.0
"""Connect the minute-based fingerprint scheduler to the existing updater."""
import json
from pathlib import Path

EN = {'fp_title': 'Fingerprint renewal', 'fp_interval': 'Check interval (minutes)', 'fp_hint': '0 = disabled', 'fp_help': 'Fingerprint check interval, in minutes. 0 disables scheduling (default). Works even when TOPG is closed.', 'fp_save': 'Save', 'fp_check': 'Check update', 'fp_update': 'Update now', 'fp_restart': 'Restart Play services', 'fp_close': 'Close', 'fp_error': 'Operation failed', 'fp_invalid': 'Enter a whole number from 0 to 10080 minutes.', 'fp_saved': 'Schedule saved', 'fp_restarted': 'Play services restart requested', 'fp_disabled': 'Scheduling disabled', 'fp_next': 'Next check:', 'fp_last': 'Last check:', 'fp_none': 'None', 'fp_ok': 'Completed'}
FR = {'fp_title': 'Renouvellement du fingerprint', 'fp_interval': 'Intervalle de vérification (minutes)', 'fp_hint': '0 = désactivé', 'fp_help': 'Intervalle de vérification du fingerprint, en minutes. 0 désactive la planification (par défaut). Fonctionne même lorsque TOPG est fermé.', 'fp_save': 'Enregistrer', 'fp_check': 'Vérifier les mises à jour', 'fp_update': 'Mettre à jour maintenant', 'fp_restart': 'Redémarrer les services Play', 'fp_close': 'Fermer', 'fp_error': 'Échec de l’opération', 'fp_invalid': 'Saisissez un entier entre 0 et 10080 minutes.', 'fp_saved': 'Planification enregistrée', 'fp_restarted': 'Redémarrage des services Play demandé', 'fp_disabled': 'Planification désactivée', 'fp_next': 'Prochaine vérification :', 'fp_last': 'Dernière vérification :', 'fp_none': 'Aucune', 'fp_ok': 'Terminé'}


def configure_fingerprint_schedule(module):
    module = Path(module)
    worker = module / 'tee/tee_start.sh'
    text = worker.read_text()
    anchor = 'sleep 1\nattempt=1'
    if text.count(anchor) != 1:
        raise RuntimeError('Fingerprint scheduler startup anchor changed')
    worker.write_text(text.replace(anchor,
        'sh "$M/tee_fingerprint_scheduler.sh" run >> "$D/fingerprint.log" 2>&1 &\n' + anchor, 1))
    web = module / 'webroot'
    index = web / 'index.html'
    html = index.read_text()
    if html.count('</body>') != 1:
        raise RuntimeError('Fingerprint scheduler WebUI anchor changed')
    index.write_text(html.replace('</body>', '<script src="tee/tee_fingerprint.js" defer></script>\n</body>', 1))
    for language, extra in [('en', EN), ('fr', FR)]:
        path = web / 'lang' / (language + '.json')
        values = json.loads(path.read_text())
        values.update(extra)
        path.write_text(json.dumps(values, ensure_ascii=False, indent=2) + '\n')
    with (web / 'lang/en.js').open('a') as fallback:
        fallback.write('\nObject.assign(window.__I18N_EN, ' + json.dumps(EN, ensure_ascii=False) + ');\n')
