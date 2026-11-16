// Presentation only: backend diagnostics and status tokens remain unchanged.
function formatUpdaterMessage(message, status = '') {
    if (status === 'up-to-date' && message === 'already on the newest build') return null;
    if (!(document.documentElement.lang || '').toLowerCase().startsWith('fr')) return message;
    const exact = {
        'Updating COPG-VD.json from GitHub...': 'Mise à jour du profil depuis GitHub…',
        'Checking GitHub for a newer build...': 'Recherche d’une version plus récente sur GitHub…',
        'Analyzing the config as it stands...': 'Analyse de la configuration actuelle…',
        'Running the updater...': 'Exécution de la mise à jour…',
        'already on the newest build': 'Le profil est déjà à jour.',
        'upstream is not newer than what is installed, nothing applied': 'La version distante n’est pas plus récente ; aucune modification.',
        'update available, fetching...': 'Nouvelle version disponible, téléchargement…',
        'props re-applied': 'Propriétés système réappliquées.',
        'could not re-apply props': 'Impossible de réappliquer les propriétés système.',
        'resetprop is disabled, props not re-applied': 'Resetprop est désactivé ; propriétés système non réappliquées.',
        'reboot to apply the new build to android.os.Build': 'Redémarrez pour appliquer le nouveau profil à android.os.Build.',
        'channel ambiguous; select a profile explicitly': 'Canal indéterminé ; sélectionnez explicitement un profil.',
        'profile fetch returned no success status': 'La récupération du profil n’a pas confirmé sa réussite.',
        'no local config to update': 'Aucune configuration locale à mettre à jour.',
        'non-numeric incremental, refusing to guess which build is newer': 'Numéro incrémental invalide ; comparaison des versions impossible.',
        'could not download index.json': 'Impossible de télécharger index.json.'
    };
    if (Object.prototype.hasOwnProperty.call(exact, message)) return exact[message];
    const patterns = [
        [/^channel: (.+) \(auto-detected\)$/, (_, channel) => `Canal : ${channel} (détection automatique)`],
        [/^channel: (.+) \(forced by argument\)$/, (_, channel) => `Canal : ${channel} (sélection explicite)`],
        [/^local:\s*(\S+) incremental (\S*) id (\S*) ts (\S*)$/, (_, device, incremental, id, ts) => `Profil local : ${device} — incrément : ${incremental}, ID : ${id}, horodatage : ${ts}`],
        [/^remote:\s*(\S+) incremental (\S*)$/, (_, device, incremental) => `Profil distant : ${device} — incrément : ${incremental}`],
        [/^local:\s*(.*)$/, (_, value) => `Profil local : ${value}`],
        [/^remote:\s*(.*)$/, (_, value) => `Profil distant : ${value}`],
        [/^update available: (.*)$/, (_, value) => `Mise à jour disponible : ${value}`],
        [/^fetched (.*) from (.*)$/, (_, profile, path) => `Profil récupéré : ${profile} — source : ${path}`],
        [/^attestation processes killed: (.*)$/, (_, packages) => `Processus d’attestation arrêtés : ${packages}`],
        [/^profile fetch failed rc=(\d+)$/, (_, code) => `Échec de récupération du profil (code ${code}).`],
        [/^no (.+) profile found for channel '(.+)' in index.json$/, (_, device, channel) => `Aucun profil ${device} pour le canal ${channel} dans index.json.`]
    ];
    for (const [pattern, replace] of patterns) {
        if (pattern.test(message)) return message.replace(pattern, replace);
    }
    return message;
}
