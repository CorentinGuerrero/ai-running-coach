# Skill : Téléchargement FIT

> **Description** : Téléchargement de fichiers FIT Garmin (et leurs records GPS en JSON) en **bypassant le canal MCP**.

## Pourquoi ce skill existe

- Le MCP Garmin (`get_activity_fit_data`) **timeoute** sur les téléchargements FIT (payloads de plusieurs Mo)
- Le script `download_fit.py` utilise la lib `garminconnect` installée dans l'environnement `garmin-mcp` + les **tokens locaux** `~/.garminconnect` → **aucun mot de passe** nécessaire

## Quand l'utiliser

- Télécharger un **fichier FIT** d'une activité Garmin
- Récupérer les **records GPS** en JSON
- Analyser une activité en détail hors du canal MCP

## Fonctionnalités

- Téléchargement de fichiers FIT via la lib `garminconnect`
- Récupération des records GPS en JSON
- Utilisation des tokens locaux (pas de mot de passe)
- **Auto-relaunch** : le script se relance dans l'environnement garmin-mcp si les dépendances manquent

## Script

`skills/fit-download/scripts/download_fit.py` — nécessite `garminconnect` + `fitparse` (disponibles dans l'environnement garmin-mcp).

Avec `--json`, écrit aussi une copie **normalisée** au chemin canonique
`activities/fit/<garmin_activity_id>.json` (unités SI, mapping documenté dans
`scripts/arc_samples.py`) — c'est ce fichier que `scripts/arc_index.py` ingère dans la
table dérivée `activity_sample` (voir [Mode headless](../dashboard/headless.md)).
Donnée brute et jetable, jamais versionnée.

## Rattraper l'historique pour la dépense énergétique modèle

Le [modèle de dépense énergétique](../energie.md) (`scripts/arc_energy.py`,
table dérivée `activity_energy`) se calcule automatiquement pour toute séance
dont le FIT est déjà ingéré — il ne manque donc **que** pour les séances plus
anciennes dont le FIT n'a jamais été téléchargé. Pour le rattraper :

1. **Télécharger les FIT manquants**, avec `--from-dir` (qui scanne tous les
   `garmin_activity_id` des `activities/*.md`) ET `--json` (indispensable :
   sans lui, seul le `.fit` brut est écrit, jamais la copie normalisée que
   `scripts/arc_index.py` ingère) :

   ```bash
   python3 skills/fit-download/scripts/download_fit.py --from-dir activities/ --json
   ```

   Une séance déjà rattrapée (sa copie normalisée
   `activities/fit/<garmin_activity_id>.json` existe déjà) est sautée
   automatiquement, même avec `--json` — relancer cette commande sur un
   historique déjà (partiellement) rattrapé ne re-télécharge donc que ce qui
   manque encore, jamais tout l'historique à chaque fois. `--overwrite` force
   quand même un nouveau téléchargement.
2. **Réindexer** : `python3 scripts/arc_index.py energy` (ou toute autre
   sous-commande — chacune réindexe le workspace au passage) recalcule alors
   `activity_energy` pour chaque séance dont le FIT vient d'être ingéré,
   automatiquement, sans étape dédiée.

**Optionnel — compléter `calories_bmr_kcal` des anciennes séances** : ce champ
(part de métabolisme de base côté Garmin) permet le calcul du NET (voir
[Dépense énergétique — brut vs net](../energie.md#brut-vs-net)) mais n'est
disponible qu'à la synchronisation — une séance ancienne peut donc avoir son
FIT rattrapé sans jamais avoir ce champ. Pour le compléter, un agent peut lire
`bmr_calories` d'une activité Garmin **une séance à la fois** (jamais une
plage) et l'ajouter au bloc ```` ```arc ```` existant du fichier
`activities/*.md` concerné. Ce n'est qu'un complément : le rattrapage du FIT
(étapes 1-2 ci-dessus) suffit déjà à obtenir le kcal BRUT du modèle, comparable
tel quel à `calories_kcal` Garmin.

**Ce n'est pas ce que fait le backfill du contrat de données** (skill
[Backfill du contrat](../skills/arc-backfill.md), CLI `scripts/arc_index.py
backfill-plan`) : celui-ci complète les fichiers Markdown dont le bloc
```` ```arc ```` est absent ou incomplet (par exemple sans
`garmin_activity_id` ou sans `calories_kcal` du tout) — un problème
DIFFÉRENT d'un FIT manquant. Une séance peut très bien avoir un bloc
```` ```arc ```` complet et valide, mais toujours pas de FIT téléchargé (donc
pas de dépense énergétique modèle) : c'est cette page-ci, pas le backfill du
contrat, qui s'applique dans ce cas.

## Fichier source

`skills/fit-download/SKILL.md`
