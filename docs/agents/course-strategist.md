# 🗺️ Agent Stratège de course

> **Description** : Course Strategy Specialist — analyse les parcours GPX ou les URL de course, construit des plans de course détaillés avec allure, nutrition, météo, matériel, et téléverse le GPX enrichi dans Garmin avec les points d'eau.

## Rôle

L'agent **course-strategist** transforme un fichier GPX ou une URL de course en un plan de course complet et actionnable.

## Workflow — 8 étapes

L'agent suit un workflow structuré en 8 étapes pour construire la stratégie de course :

1. **Analyse du parcours** — à partir d'un fichier GPX ou d'une URL de course
2. **Points d'eau et ravitaillement** — via OpenStreetMap
3. **Allures par segment et 3 scénarios** — sécurité, réaliste, ambitieux, depuis
   le modèle personnel pente → allure quand un GPX est fourni (`scripts/arc_race_pacing.py`, #59) ;
   règles génériques en repli (URL seule, sans GPX)
4. **Plan de nutrition** — ravitaillement en course
5. **Plan d'hydratation** — gestion des liquides
6. **Préparation météo** — conditions attendues
7. **Préparation matériel** — équipement nécessaire
8. **Push dans Garmin** — téléversement du GPX enrichi avec les waypoints

## Alignement avec l'objectif

- **Contexte** : aligne toujours la stratégie de course avec l'objectif actif dans `planning/active_objective.md`
- **Mise à jour** : propose de mettre à jour `planning/active_objective.md` si la course devient le nouvel objectif principal

## Gestion des données

- **Rafraîchissement contextuel** : vérifie `planning/`, `activities/`, `medical/` et `resources/` avant d'analyser
- **Persistance** : stocke chaque plan de course dans `planning/` et le plan nutritionnel dans `nutrition/`
- **Langue** : les fichiers MD utilisent la langue configurée dans `config/workspace.toml` (`[language].documents`, défaut : français)

## Skills utilisés

| Skill | Quand |
|---|---|
| `gpx-analysis` | analyse du parcours GPX |
| `course-comparison` | comparaison avec des parcours connus |
| `weather-forecast` | préparation météo |
| `garmin-workout-scheduling` | push de la séance dans Garmin |

## Allures par segment (#59)

Quand un GPX est fourni, l'agent délègue le calcul des allures à
`scripts/arc_race_pacing.py plan` plutôt que d'estimer à la main : découpage du
parcours en segments (distance cible fusionnée par pente similaire), intégré
point par point (pas la seule pente moyenne — un aller-retour compte plus
qu'un plat) pour prédire le temps de chaque segment depuis le modèle personnel
pente → allure (`scripts/arc_slope_model.py`, #58), mis à l'échelle de
l'intensité de COURSE visée (Riegel/VDOT, `scripts/arc_metrics.py`, #33 —
`arc_slope_model` ne connaît que l'allure d'ENDURANCE d'entraînement). Fade de
fin de course depuis la durabilité récente (`scripts/arc_durability.py`, #48,
ou un repli générique signalé comme tel, échelonné à la durée réelle de la
course), ajustement chaleur/acclimatation (#38) et vérification des barrières
horaires (formats `HH:MM`, `+HH:MM` élapsé ou date-heure ISO 8601 pour un
ultra multi-jours). Chaque segment porte sa **provenance**
(`personal`/`generic`/`mixed`) — le plan la cite explicitement, jamais un
scénario qui prétendrait à une précision que l'historique ne permet pas ; un
GPX sans altitude exploitable déclenche un avertissement explicite (`warnings`)
plutôt qu'un plan silencieusement faux. Persisté dans le champ `segments` du
bloc ```arc `race_plan` (voir
[le skill `workspace-data-contract`](../skills/workspace-data-contract.md)) —
socle du futur débrief post-course segment par segment.

## Fichier source

`agents/course-strategist.md` · moteur : `scripts/arc_race_pacing.py`
