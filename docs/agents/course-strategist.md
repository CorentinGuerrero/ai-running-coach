# Agent Stratège de course

> **Description** : Course Strategy Specialist — analyse les parcours GPX ou les URL de course, construit des plans de course détaillés avec allure, nutrition, météo, matériel, et téléverse le GPX enrichi dans Garmin avec les points d'eau.

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
7. **Équipement et vêtements** — checklist détaillée (lampe frontale, chaussures, hydratation, matériel obligatoire)
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
la durée réelle de la course), ajustement chaleur/acclimatation (#38) et
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

## Fichier source

`agents/course-strategist.md` · moteur : `scripts/arc_race_pacing.py`
