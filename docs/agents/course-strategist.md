# Agent Stratège de course

> **Description** : Course Strategy Specialist — analyse les parcours GPX ou les URL de course, construit des plans de course détaillés avec allure, nutrition, météo, matériel, et téléverse le GPX enrichi dans Garmin avec les points d'eau.

<!-- arc-video:jour-de-course -->
<div class="arc-video-card" markdown>

[![La course, segment par segment](../video/jour-de-course/poster.jpg)](../video/jour-de-course/index.html)

<div markdown>

<span class="arc-video__meta">En vidéo · Étape 06 · 1 min 43</span>

**[La course, segment par segment](../video/jour-de-course/index.html)** — Du GPX au plan de course : allures par segment, énergie, matériel obligatoire, montre, puis débrief plan contre réalisé.

[Regarder](../video/jour-de-course/index.html) · [English](../video/jour-de-course/index.html?lang=en) · [Toutes les vidéos](../videos.md)

</div>

</div>
<!-- /arc-video -->


## Rôle

L'agent **course-strategist** transforme un fichier GPX ou une URL de course en un plan de course complet et actionnable.

## Workflow — 8 étapes

L'agent suit un workflow structuré en 8 étapes pour construire la stratégie de course :

1. **Analyse d'entrée** — GPX (analyse générique via le skill `gpx-analysis`) ou URL de course (extraction via `webfetch`)
2. **Points d'eau et ravitaillement** — points officiels + enrichissement OpenStreetMap (Overpass), alertes sur les écarts > 8 km / > 15 km
3. **Vérification et questions utilisateur** — comble les informations critiques manquantes (barrières horaires, terrain, points d'eau proposés) avant de continuer
4. **Synthèse allures et temps de passage** — 3 scénarios (ambitieux, réaliste, sécurité), par segment depuis le modèle personnel pente → allure quand un GPX est fourni (`scripts/arc_race_pacing.py`, #59) ; règles génériques en repli (URL seule, sans GPX)
5. **Plan de nutrition** — objectif glucides/h (plafonné au débit toléré à l'entraînement, #41), hydratation, produits réels si un catalogue est fourni
6. **Météo** — si la course est à ≤ 14 jours, ajustements automatiques et acclimatation à la chaleur (#38)
7. **Équipement et vêtements** — checklist détaillée (lampe frontale, chaussures, hydratation, matériel obligatoire), puis **contrôle du matériel de course** (#134) : la liste `gear` du plan est croisée avec l'inventaire du profil (`arc_index.py equipment --race-plan`) — objets **manquants** (« non retrouvé dans votre inventaire »), **à vérifier** (seule la catégorie correspond — jamais donné pour conforme), **jamais utilisés à l'entraînement** (« rien de nouveau le jour J ») ou **sous alerte** ; le rapprochement est textuel strict et rien n'est jamais inventé (inventaire non déclaré = dit tel quel)
8. **Upload Garmin** — GPX enrichi (waypoints des ravitaillements) téléversé via `upload_course`

## Alignement avec l'objectif

- **Contexte** : aligne toujours la stratégie de course avec l'objectif actif dans `planning/active_objective.md`
- **Mise à jour** : propose de mettre à jour `planning/active_objective.md` si la course devient le nouvel objectif principal

## Gestion des données

- **Rafraîchissement contextuel** : vérifie `planning/`, `activities/`, `medical/` et `resources/` avant d'analyser
- **Persistance** : stocke chaque plan de course dans `planning/` et le plan nutritionnel dans `nutrition/`
- **Langue** : les fichiers MD utilisent la langue configurée dans `config/workspace.toml` (`[language].documents`, défaut : français)
- **Indice de performance (#62)** : peut citer l'indice ITRA/UTMB déclaré dans le profil comme un repère qualitatif parmi d'autres pour choisir un scénario d'allure — jamais de conversion inventée indice → allure, et jamais de recherche automatique sur `itra.run`/`utmb.world` (uniquement sur demande explicite, voir l'agent `coach`)

## Skills utilisés

| Skill | Quand |
|---|---|
| `gpx-analysis` | analyse du parcours GPX (étape 1) |
| `weather-forecast` | préparation météo (étape 6, course à ≤ 14 jours) |
| `workspace-data-contract` | avant d'écrire un plan de course dans `planning/` ou un plan nutrition dans `nutrition/` |

## Allures par segment (#59)

Quand un GPX est fourni, l'agent délègue le calcul des allures à
`scripts/arc_race_pacing.py plan` plutôt que d'estimer à la main : découpage du
parcours en segments (distance cible fusionnée par pente similaire), intégré
point par point (pas la seule pente moyenne — un aller-retour compte plus
qu'un plat) pour prédire le temps de chaque segment depuis le modèle personnel
pente → allure (`scripts/arc_slope_model.py`, #58), mis à l'échelle de
l'intensité de COURSE visée — Riegel depuis un effort RÉCENT et DUR (tempo/
seuil/VO2max/course, jamais un simple footing) converti en équivalent plat des
deux côtés, VDOT en repli (`scripts/arc_metrics.py`, #33 — `arc_slope_model`
ne connaît que l'allure d'ENDURANCE d'entraînement), calculée sur le GPX
analysé, jamais sur `planning/active_objective.md`. Fade de fin de course
depuis la durabilité récente (`scripts/arc_durability.py`, #48, rendu NEUTRE
en temps total quand Riegel/VDOT s'applique déjà — jamais une double
dégradation d'endurance — ou un repli générique signalé comme tel, échelonné à
la durée réelle de la course), ajustement chaleur/acclimatation (#38), pénalité de nuit (#184, voir ci-dessous) et
vérification des barrières
horaires (formats `HH:MM`, `+HH:MM` élapsé ou date-heure ISO 8601 pour un
ultra multi-jours). Chaque segment porte sa **provenance**
(`personal`/`generic`/`mixed`) — le plan la cite explicitement, jamais un
scénario qui prétendrait à une précision que l'historique ne permet pas ; un
GPX sans altitude exploitable déclenche un avertissement explicite (`warnings`)
plutôt qu'un plan silencieusement faux. Persisté dans le champ `segments` du
bloc ```arc `race_plan` (voir
[le skill `workspace-data-contract`](../skills/workspace-data-contract.md)) —
socle du débrief post-course segment par segment (`scripts/arc_race_debrief.py`,
#61 : voir [l'agent Coach](coach.md)).

## Pénalité de nuit (#184)

Sur un ultra, une partie de la course se court de nuit. Avec `--race-date`, un
`--start` explicite et `--tz` (fuseau IANA, ex. `Europe/Paris`),
`scripts/arc_race_pacing.py plan` calcule **localement, sans réseau**
(`scripts/arc_solar.py`, algorithme NOAA — approximation de l'ordre de la
minute) le crépuscule civil du lieu (premier point du GPX) et la **fraction de
nuit** de chaque section, scénario par scénario, d'après son heure d'horloge
réelle (départ, temps de section déjà pénalisés, arrêts ravito). Le temps de la
section est multiplié par `night_factor` = 1 + fraction de nuit × pénalité :
**5 %** à pleine nuit à plat/en montée, jusqu'à **+8 points** en descente
(0,6 point par % de pente au-delà de 2 %) — des **approximations du projet**,
aucune source vérifiée ne les chiffre pour un athlète donné ; réglables
(`--night-penalty-pct`, `--night-descent-extra-max-pct`) ou désactivables
(`--no-night`), et à recalibrer au débrief (#188). Le calcul itère (la pénalité
décale les sections suivantes) jusqu'à convergence, bornée à 8 passes, et garde
toujours `prudent ≥ réaliste ≥ ambitieux` section par section.

La sortie ajoute `night_fraction`/`night_factor` par section et par scénario,
et un objet `night` : `status` (`night`, `daylight`, `unavailable`,
`disabled`), `scenarios[...].summary` (« 6,8 h de nuit, frontale requise de
17:32 à 00:18 (J+1) ») et `gear_hint`. **Si la date, l'heure de départ
explicite ou le fuseau manquent, aucun facteur de nuit n'est appliqué, la sortie
reste identique à celle d'avant et `night.reason` le dit** — jamais une nuit
supposée. Une course entièrement de jour n'ajoute aucun champ par section. Le
contrôle de la frontale dans le matériel obligatoire reste celui de
`arc_index.py equipment --race-plan` (#134).

## Dépense énergétique prévue par section

La sortie de `scripts/arc_race_pacing.py plan` porte aussi `energy` (kcal,
kcal/h et cumul par segment, pour chacun des trois scénarios) — un contrôle/
outil de PRÉVISION indépendant, calculé depuis le même moteur RE3 + Minetti
que le contrôle post-séance de l'agent `coach` (`scripts/arc_energy.py`).
`--pack-kg` (poids du sac/flasques/matériel porté) est nécessaire pour
un résultat fidèle — l'agent le demande à l'athlète, ou dit explicitement
qu'il l'estime faute de réponse ; sans lui, le calcul suppose 0 kg et le
signale dans `warnings`. Un poids d'athlète introuvable
(`energy.available == false`) n'invalide jamais le reste du plan. L'agent met
le kcal/h prévu par section en regard du plan de ravitaillement (étape 5) pour
signaler un déficit horaire/cumulé, sans jamais prétendre qu'il doit être
comblé intégralement — qualitatif faute d'une source vérifiable sur la part
couverte par les réserves de l'athlète. `energy` reste un KPI DÉRIVÉ exposé
par la CLI, jamais une clé du contrat `race_plan` persisté (même statut que
`scripts/arc_index.py fueling`).

**Calibration personnelle** : chaque scénario, et chaque section à
l'intérieur de ce scénario, porte à côté des valeurs brutes
(`kcal`/`kcal_per_h`/`cumulative_kcal`) leurs équivalents
`kcal_calibrated`/`kcal_per_h_calibrated`/`cumulative_kcal_calibrated` — un
facteur personnel (`energy.calibration`, `{"band", "band_source", "n",
"ratio_median", "ratio_iqr", "status", "factor"}`) appris sur l'écart
Garmin/modèle mesuré de l'athlète. Le panier (route ou trail) est choisi
depuis le D+/km réel du GPX analysé (`band_source == "gpx"`), ou forcé
explicitement par `--terrain road|trail` (`band_source == "option"`) — jamais
depuis le profil général de l'athlète, voir [Dépense énergétique — la
calibration personnelle](../energie.md#la-calibration-personnelle). L'agent
utilise TOUTES les valeurs calibrées (jamais un mélange avec les brutes)
uniquement quand `status == "applied"` (échantillon suffisant, écart non
négligeable) ; sinon toutes les valeurs brutes — jamais présentées comme une
mesure quand calibrées.

## Fichier source

`agents/course-strategist.md` · moteur : `scripts/arc_race_pacing.py`
