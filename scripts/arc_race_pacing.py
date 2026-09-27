#!/usr/bin/env python3
"""Allures de course par segment depuis le modèle personnel pente -> allure
(#59, épopée #23).

## Pourquoi

Les scénarios ×3 du plan de course (`agents/course-strategist.md`) reposaient
sur des règles génériques (« +2-3 % par 10 km », « sable -> ×1.2-1.3 »),
jamais sur l'historique réel de l'athlète. Ce module consomme les briques déjà
posées par les épopées précédentes — `arc_slope_model.predict_speed` (#58,
courbe personnelle pente -> allure), `arc_durability` (#48, fade de fin de
sortie longue), `arc_metrics.predictions` (#33, Riegel/VDOT) — et les combine
à un fichier GPX de course pour produire des temps de passage PAR SEGMENT,
avec leur provenance (personnel vs générique), trois scénarios documentés et
une vérification de barrières horaires.

Sert aussi de socle à #61 (débrief post-course, comparaison plan vs réalisé
PAR SEGMENT) : les identifiants de segment (`s01`, `s02`…) et leurs bornes
kilométriques sont stables d'un appel à l'autre pour un même GPX et un même
`--segment-m` (déterminisme, voir `ASSUMPTIONS["segmentation"]`) — #61 doit
pouvoir aligner un segment du plan avec le même segment mesuré après course
sans recalculer sa propre segmentation.

## Découpage en couches (comme le reste du moteur)

- **Segmentation** (`segment_course`) : pure, ne dépend que du GPX (via
  `arc_elevation.grade_series`, déjà partagé par le GAP/#44 et l'analyse GPX
  générique du skill `gpx-analysis`). Conserve, en plus des champs publics du
  contrat, un profil pente/distance POINT PAR POINT (clé privée `_profile`,
  jamais émise dans le JSON final) — voir `ASSUMPTIONS["rolling_terrain"]`
  pour pourquoi la moyenne de pente seule ne suffit pas.
- **Prédiction** (`predict_segments`) : pure, ne dépend que des segments, des
  paniers du modèle personnel (`arc_slope_model.predict_speed`), d'un taux de
  fade, d'un facteur météo et d'un facteur d'intensité de course déjà résolus
  par l'appelant — aucun accès disque ni réseau ici.
- **Passages/barrières** (`compute_passages`/`check_cutoffs`) : pures, cumul
  des temps de segment + arrêts ravito, comparaison aux barrières horaires.
- **CLI** (`plan`, fonction `main`) : la SEULE couche qui touche le disque —
  lit le GPX, ouvre l'index du workspace UNE SEULE FOIS (`arc_index`, mêmes
  conventions que les autres sous-commandes : `--workspace`, `--db`,
  `--memory`, `--rebuild`, `--today`) pour résoudre le modèle personnel, la
  tendance de durabilité, l'intensité de course et l'acclimatation chaleur,
  et assemble le JSON final.

## Pourquoi un script séparé plutôt qu'une sous-commande `arc_index.py`

Même logique que `skills/gpx-analysis/scripts/analyze_gpx.py` et
`skills/course-comparison/scripts/compare_course.py` (#59 ne rompt pas cette
convention) : ce script combine un fichier EXTERNE fourni à l'appel (le GPX de
la course, jamais indexé) avec des paramètres de scénario (date de course,
heure de départ, ravitos, météo prévue) qui n'ont pas de sens comme requête
sur l'index seul — contrairement à `slope-model`/`durability`, qui ne lisent
QUE l'historique déjà indexé. `arc_race_pacing.py` IMPORTE `arc_index` comme
bibliothèque (même précédent que `arc_serve.py`/`arc_guardrails.py`/
`coach_doctor.py`) pour réutiliser sa résolution de workspace/config et ses
rapports `slope_model_report`/`durability_trend`/`heat_acclimation_today`,
jamais une seconde implémentation de ces calculs. L'index n'est ouvert et
reconstruit QU'UNE SEULE FOIS par appel CLI (revue de code #59 : trois
réindexations indépendantes coûtaient ≈ 7,6 s contre ≈ 2,5 s pour une seule) —
`main()` ouvre `conn` et le passe à chaque résolveur, aucun résolveur
n'importe plus `arc_index` lui-même.

## Segmentation (voir `ASSUMPTIONS["segmentation"]`)

Longueur cible fixe (`--segment-m`, défaut 750 m — au milieu de la fourchette
500 m-1 km demandée par #59), puis une passe de fusion GREEDY de gauche à
droite : deux segments adjacents dont la pente moyenne diffère de moins de
`MERGE_GRADE_DELTA_PCT` (2 points) sont fusionnés, tant que le segment fusionné
ne dépasse pas `MAX_SEGMENT_FACTOR` × la longueur cible (2250 m par défaut) —
évite une avalanche de tout petits segments sur un profil plat tout en gardant
un côté déterministe et un plafond de longueur pour ne jamais dissoudre une
vraie rupture de pente dans un segment démesuré. Cette même passe couvre
maintenant aussi le DERNIER segment (revue de code #59 : l'ancienne fusion
inconditionnelle du reliquat final ignorait la pente) ; un reliquat encore
trop court après la fusion par pente (`MIN_SEGMENT_M`, 300 m) est fusionné
dans le précédent en dernier recours, quelle que soit sa pente — jamais un
segment orphelin, mais seulement quand la fusion « intelligente » n'a pas
suffi.

## Terrain vallonné : intégration point par point (voir `ASSUMPTIONS["rolling_terrain"]`)

La pente MOYENNE d'un segment (`grade_mean_pct`, conservée pour l'affichage)
ne suffit PAS à prédire son temps : un aller-retour +12 %/-12 % tous les
375 m dans un même segment de 750 m a une pente moyenne quasi nulle mais un
temps réel bien plus long qu'un vrai plat (le coût d'une montée n'est jamais
compensé par le gain symétrique d'une descente à la même pente, voir
`arc_gap.ASSUMPTIONS["model"]`). Le temps prédit intègre donc `Δd / v(pente
locale)` sur CHAQUE paire de points GPX du segment (pente lissée de
`arc_elevation.grade_series`), jamais sur la seule pente moyenne.

## Fade (voir `ASSUMPTIONS["fade"]`)

Le fade GAP médian des sorties longues récentes (`arc_durability`, #48) est
appliqué comme un ralentissement PROGRESSIF, calibré pour que la MOYENNE du
ralentissement sur le DERNIER TIERS de la course égale `fade_pct` (même
définition que la mesure source, qui compare premier et dernier tiers) —
nul sur le premier tiers, rampe linéaire ensuite. Échelonné en plus par la
durée de course PRÉDITE face au seuil de sortie longue
(`arc_metrics.LONG_RUN_MIN_DURATION_S`, 90 min) : un fade mesuré sur des
sorties de plus de 90 minutes n'a pas de raison de s'appliquer PLEINEMENT à
une course de 30 minutes.

## Chaleur (voir `ASSUMPTIONS["heat"]`)

Reprend TELS QUELS les seuils déjà documentés dans `agents/course-strategist.md`
(ÉTAPE 6, approximation du projet, jamais une source physiologique
vérifiable pour ces pourcentages précis) : > 25 °C -> +10 % de temps,
< 5 °C -> +5 % de temps — avec un supplément de +5 % si la course est prévue
chaude ET que l'athlète a peu été exposé à la chaleur récemment
(`arc_index.heat_acclimation_today`, #38) : un pari optimiste sur une
acclimatation supposée serait plus dangereux qu'un plan trop prudent.

## Allure de BASE : endurance mise à l'échelle de l'intensité de course (voir `ASSUMPTIONS["base_pace"]`)

`arc_slope_model.predict_speed` rend une allure de la bande « endurance »
(effort facile) — jamais l'allure de COURSE visée, qui est en général bien
plus rapide. `intensity_factor` corrige cette différence : rapport entre la
vitesse plate ÉQUIVALENTE prédite pour la course (Riegel, à partir du
meilleur effort récent — voir `ASSUMPTIONS["base_pace"]`) et la référence
plate personnelle de la bande endurance. Sans objectif chiffré ou sans
historique suffisant pour une prédiction, le facteur reste `1.0`
(`intensity_source: "none"`) et le plan reste explicitement une allure
D'ENDURANCE, jamais une allure de course inventée.

## Scénarios (voir `ASSUMPTIONS["scenarios"]`)

Quand un segment est prédit par le modèle PERSONNEL, les trois scénarios
utilisent directement la dispersion déjà calculée par panier
(`arc_slope_model` : IQR pondéré p25/p50/p75, exposé par `predict_speed` comme
`ci_low_speed_ms`/`speed_ms`/`ci_high_speed_ms`) — jamais un pourcentage
inventé quand une vraie dispersion mesurée existe, mais JAMAIS plus ÉTROITE
non plus que l'écart générique documenté (`GENERIC_SCENARIO_SPEED_FACTOR`,
±6-8 %, revue de code #59 : un historique de deux sorties à allure quasi
identique ne doit pas produire un écart quasi nul entre scénarios). Un
segment générique ou mixte (pas de dispersion, `ci_*` à `None`) retombe
directement sur ce pourcentage fixe documenté, signalé comme approximation du
projet.

Jamais de fausse précision : les temps de segment sont arrondis à la seconde
la plus proche (une fraction de seconde n'a aucun sens physique) mais les
temps de passage CUMULÉS et les totaux sont arrondis à la MINUTE la plus
proche — un plan de course n'a jamais la précision de la seconde sur
plusieurs heures d'effort.

Stdlib uniquement (CONTRIBUTING.md).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arc_contract as C  # noqa: E402
import arc_elevation as EL  # noqa: E402
import arc_metrics as M  # noqa: E402
import arc_slope_model as SL  # noqa: E402

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_SEGMENT_M = 750.0
MIN_SEGMENT_M = 300.0
MAX_SEGMENT_FACTOR = 3.0
MERGE_GRADE_DELTA_PCT = 2.0  # points de pourcentage
DEFAULT_BAND = "endurance"
DEFAULT_FADE_WEEKS = 12  # même fenêtre par défaut que decoupling/vam/descent/durability

# Référence Riegel (revue de code #59, BLOQUANT) : seules les intensités
# planifiées d'un effort RÉELLEMENT dur (tempo et au-delà) qualifient une
# activité comme référence de vitesse de COURSE — un footing facile, même
# long, sous-estime largement l'allure de course et produirait une prédiction
# plus LENTE que l'allure d'endurance elle-même. Mêmes valeurs que
# `arc_contract.INTENSITY`, sous-ensemble « dur ».
HARD_REFERENCE_INTENSITIES = ("tempo", "threshold", "vo2max", "race")
# Distance minimale d'une référence Riegel — même seuil que
# `arc_metrics.predictions`/`RECORD_DISTANCES_KM` (`km >= 5` = « le plus long
# effort est le plus prédictif »).
MIN_REFERENCE_DISTANCE_M = 5000.0
# En dessous de ce seuil, un `intensity_factor` calculé sous 1.0 (allure de
# course plus LENTE que l'allure d'endurance mesurée) est implausible et
# plafonné à 1.0 (revue de code #59, BLOQUANT) — au-delà, l'exposant de Riegel
# en trail (1.15, `arc_metrics.RIEGEL_EXPONENT`) prédit déjà, à raison, un
# ralentissement marqué sur un ultra : aucun plancher n'y est nécessaire.
INTENSITY_CLAMP_DURATION_S = 4.5 * 3600.0
# Écart (%) entre l'objectif chiffré (`planning/active_objective.md`) et le GPX
# réellement analysé, en équivalent plat, au-delà duquel un avertissement est
# émis — l'intensité de course est TOUJOURS calculée depuis le GPX (revue de
# code #59, BLOQUANT), jamais depuis l'objectif, qui peut décrire une autre
# course ou une distance arrondie.
OBJECTIVE_GPX_MISMATCH_PCT = 10.0

# Clés EN ANGLAIS (contrat ```arc, AGENTS.md « clés en anglais ») — mêmes noms
# que `race_plan.scenarios` déjà défini par le skill `workspace-data-contract`
# (`{"ambitious": s, "realistic": s, "safe": s}`) : un plan de course par
# segment doit utiliser le même vocabulaire de scénario que le plan global,
# jamais un second jeu de noms pour la même notion. "safe" = prudent (le plus
# lent), "realistic" = cible (médiane/interpolation), "ambitious" = ambitieux
# (le plus rapide).
SCENARIOS = ("safe", "realistic", "ambitious")

# Approximation du projet (revue de code #59) : AUCUNE source vérifiable ne
# documente ces pourcentages précis pour un athlète sans dispersion mesurée —
# ils encadrent la cible d'un ordre de grandeur raisonnable (±6-8 %). Sert
# AUSSI d'écart PLANCHER pour un segment personnel dont la dispersion mesurée
# serait plus étroite (revue de code #59, voir `_scenario_speeds`) : jamais une
# vraie mesure de dispersion individuelle, mais jamais un signal de confiance
# artificiellement optimiste non plus.
GENERIC_SCENARIO_SPEED_FACTOR = {"safe": 0.92, "realistic": 1.0, "ambitious": 1.06}

# Fade générique de repli (#59, ASSUMPTIONS["fade"]) : appliqué UNIQUEMENT si
# aucune sortie longue récente n'a de fade GAP mesurable (`arc_durability`) —
# approximation du projet, pas une mesure. Volontairement modeste : un plan de
# course ne doit pas supposer un effondrement qu'aucune donnée ne suggère.
DEFAULT_GENERIC_FADE_PCT = 5.0

# Calibration du profil de fade (revue de code #59) : `fade_speed_multiplier`
# rampe linéairement à partir du premier tiers de course — un simple facteur
# ×1 à l'arrivée ne fait, en MOYENNE sur le dernier tiers, que 0,75 × `fade_pct`
# (aire d'un triangle), alors que `fade_pct` est défini par `arc_durability`
# comme la MOYENNE du dernier tiers. `FADE_LAST_THIRD_MEAN_FACTOR` (4/3) est le
# facteur qui rend cette moyenne exacte : voir `ASSUMPTIONS["fade"]` pour le
# calcul complet.
FADE_LAST_THIRD_MEAN_FACTOR = 4.0 / 3.0
# Plancher de sécurité (jamais une vitesse nulle ou négative) pour un `fade_pct`
# extrême — approximation du projet, pas une mesure.
FADE_MIN_SPEED_FACTOR = 0.05

# Seuils météo — repris TELS QUELS de `agents/course-strategist.md` (ÉTAPE 6),
# approximation du projet documentée là, jamais une source physiologique
# vérifiable pour ces pourcentages précis.
HEAT_HOT_C = 25.0
HEAT_COLD_C = 5.0
HEAT_HOT_TIME_FACTOR = 1.10
HEAT_COLD_TIME_FACTOR = 1.05
# Supplément si la course est prévue chaude ET que l'athlète a peu été exposé
# à la chaleur récemment (#38) — approximation du projet, pas une mesure.
HEAT_UNACCLIMATED_EXTRA_FACTOR = 1.05
HEAT_ACCLIMATION_MIN_HOT_SESSIONS = 2

# Ravitaillement : temps d'arrêt par défaut si non précisé par station (#59) —
# approximation du projet (un ravito simple, ni drop bag ni repas chaud).
DEFAULT_AID_STATION_STOP_S = 90.0

# Barrière horaire : marge de confort avant de considérer un scénario comme
# "tendu" plutôt que "confortable" — approximation du projet, jamais une règle
# de course réelle (chaque course a ses propres marges de sécurité).
CUTOFF_MARGIN_OK_S = 30 * 60

# Arrondis (revue de code #59, honnêteté de la précision affichée) : un temps
# de SEGMENT à la seconde la plus proche, un temps de PASSAGE/TOTAL cumulé à
# la minute la plus proche — jamais l'inverse, jamais les deux à la seconde.
SEGMENT_ROUND_S = 1
PASSAGE_ROUND_S = 60


def _round_passage(seconds: float) -> int:
    return int(round(seconds / PASSAGE_ROUND_S)) * PASSAGE_ROUND_S


ASSUMPTIONS = {
    "segmentation": (
        "Segments de longueur cible fixe (`DEFAULT_SEGMENT_M`, 750 m — milieu de la fourchette "
        "500 m-1 km demandée par #59), pente moyenne calculée par distance parcourue (pondérée) sur "
        "le profil d'altitude lissé (`arc_elevation.grade_series`, fenêtre 30 m, même moteur que le "
        "GAP #44 et l'analyse GPX générique du skill gpx-analysis). Une passe de fusion GREEDY, de "
        "gauche à droite, fusionne deux segments adjacents (dernier compris, revue de code #59) dont la "
        "pente moyenne diffère de moins de `MERGE_GRADE_DELTA_PCT` (2 points), tant que le segment "
        "fusionné ne dépasse pas `MAX_SEGMENT_FACTOR` × la longueur cible (2250 m par défaut) — réduit "
        "la fragmentation sur un profil plat sans jamais dissoudre une vraie rupture de pente dans un "
        "segment démesuré. Un reliquat encore plus court que `MIN_SEGMENT_M` (300 m) APRÈS cette passe "
        "est fusionné dans le précédent en dernier recours, quelle que soit sa pente — jamais un "
        "segment orphelin, mais seulement quand la fusion par pente n'a pas suffi. Déterministe pour un "
        "GPX et un `--segment-m` donnés : mêmes identifiants (`s01`, `s02`…) et mêmes bornes "
        "kilométriques d'un appel à l'autre — propriété nécessaire à #61 (débrief post-course par "
        "segment)."
    ),
    "rolling_terrain": (
        "La pente MOYENNE d'un segment (`grade_mean_pct`, conservée pour l'affichage) ne suffit PAS à "
        "prédire son temps (revue de code #59, blocant) : un profil vallonné (+12 %/-12 % tous les "
        "375 m dans un segment de 750 m) a une pente moyenne quasi nulle mais un temps réel bien plus "
        "long qu'un vrai plat — le coût métabolique d'une montée n'est jamais compensé par le gain "
        "symétrique d'une descente à la même pente (modèle de Minetti, voir "
        "`arc_gap.ASSUMPTIONS['model']`) ; moyenner la pente AVANT de prédire la vitesse revient à "
        "prédire la vitesse d'un plat qui n'existe pas. `predict_segments` intègre donc `Δd / "
        "v(pente locale)` sur CHAQUE paire de points GPX consécutifs du segment (pente lissée de "
        "`arc_elevation.grade_series`, moyenne des deux pentes d'extrémité de la paire), jamais sur la "
        "seule pente moyenne — `grade_mean_pct` reste UNIQUEMENT un repère d'affichage. Une pente qui "
        "tombe dans l'intervalle `[lo, hi)` d'un panier PERSONNEL du modèle est en plus SNAPÉE "
        "EXACTEMENT sur le point milieu de ce panier avant la prédiction (`_snap_grade_to_bin`, 2ᵉ revue "
        "de code #59, should-fix) : sans ce snap, `predict_speed` interpole entre deux paniers voisins "
        "dès que la pente n'est pas EXACTEMENT sur un point milieu, étiquetant à tort `\"mixed\"` un "
        "point qui tombe pourtant bien dans la plage MESURÉE d'un panier personnel — jusqu'à 58 % de "
        "segments `\"mixed\"` observés sur un profil trail synthétique dont les pentes de 1-2 % "
        "tombaient hors du seul panier central snappé par la première version de ce correctif. Repli, "
        "pour un `bins` de test sans `grade_lo`/`grade_hi` (ou si aucun panier personnel ne couvre la "
        "pente) : neutralise seulement le panier CENTRAL canonique du modèle "
        "(`arc_slope_model.GRADE_BINS`), pour ne jamais interpoler un bruit GPS de quelques dixièmes de "
        "point autour du plat."
    ),
    "scenarios": (
        "Un segment prédit par le modèle PERSONNEL (`source == \"personal\"`) utilise directement la "
        "dispersion déjà calculée par panier de pente (`arc_slope_model`, IQR pondéré p25/p50/p75, "
        "exposée par `predict_speed` comme `ci_low_speed_ms`/`speed_ms`/`ci_high_speed_ms`) : "
        "« safe » = p25 (plus lent), « realistic » = médiane/interpolation, « ambitious » = p75 (plus "
        "rapide) — jamais un pourcentage inventé quand une vraie dispersion mesurée existe. Cette "
        "dispersion mesurée ne peut cependant jamais être PLUS ÉTROITE que l'écart générique documenté "
        "(`GENERIC_SCENARIO_SPEED_FACTOR`, ±6-8 % — revue de code #59, should-fix) : deux sorties "
        "d'entraînement à allure quasi identique produisent un IQR quasi nul, ce qui donnerait trois "
        "scénarios pratiquement confondus — un signal de confiance que rien ne justifie sur seulement "
        "deux séances. `safe` est donc le MINIMUM (le plus lent) entre la borne p25 mesurée et "
        "`speed × 0.92`, `ambitious` le MAXIMUM (le plus rapide) entre la borne p75 mesurée et "
        "`speed × 1.06` — la mesure l'emporte seulement quand elle est PLUS large que le plancher "
        "générique, jamais quand elle est plus étroite. Un segment générique ou mixte (`ci_*` à "
        "`None`) retombe directement sur ce pourcentage fixe, signalé comme approximation du projet, "
        "sans source vérifiable pour ces valeurs précises."
    ),
    "base_pace": (
        "`arc_slope_model.predict_speed` (#58) est ajusté sur la bande « endurance » (effort facile "
        "d'entraînement) : ses vitesses ne sont PAS l'allure de COURSE visée, en général nettement plus "
        "rapide (revue de code #59, blocant — cette distinction n'était affichée nulle part). "
        "`intensity_factor` corrige l'écart : `(vitesse plate équivalente prédite pour la course) / "
        "(référence plate personnelle de la bande endurance, slope_model_report."
        "flat_reference_speed_ms)`.\n\n"
        "**Cible = le GPX analysé, jamais l'objectif** (2ᵉ revue de code #59, BLOQUANT) : la vitesse "
        "plate cible se calcule sur `distance_m`/`elevation_gain_m` mesurés du GPX (équivalence plat "
        "trail : `arc_metrics.TRAIL_FLAT_M_PER_M_DPLUS`), jamais sur `planning/active_objective.md` — "
        "un objectif qui décrit une autre course, ou une distance arrondie, aurait sinon faussé le "
        "facteur sans rapport avec le parcours réellement chargé. Si `planning/active_objective.md` "
        "existe et diffère de plus de `OBJECTIVE_GPX_MISMATCH_PCT` (10 %) du GPX en équivalent plat, un "
        "avertissement le signale dans `warnings` — l'objectif reste alors purement informatif.\n\n"
        "**Référence = un effort RÉEL et DUR, jamais un footing facile** (2ᵉ revue de code #59, "
        "BLOQUANT) : un simple filtre « le plus long effort connu » (l'ancienne méthode) retenait "
        "parfois une longue sortie d'ENDURANCE vallonnée comme référence de vitesse de COURSE — sa "
        "pente ralentit déjà la référence (aucune conversion plate n'était appliquée côté référence), "
        "ET la courbe pente -> allure la ralentit une seconde fois sur les segments en côte du plan : un "
        "double comptage qui pouvait rendre l'allure de « course » plus LENTE que l'allure d'endurance "
        "mesurée. La référence Riegel n'est donc retenue que parmi les activités course à pied "
        "d'au moins `MIN_REFERENCE_DISTANCE_M` (5 km) dont l'intensité planifiée "
        "(`arc_index.planned_intensity_for`) est dans `HARD_REFERENCE_INTENSITIES` (tempo/seuil/VO2max/"
        "course), ou, à défaut de plan, dont la FC moyenne dépasse la borne Z3/Z4 de l'athlète "
        "(`arc_index.athlete_hr_zone_bounds`) — la plus longue qualifiante est la plus prédictive (même "
        "principe que `arc_metrics.predictions`). Sa distance ET son D+ propres sont convertis en "
        "équivalent plat EXACTEMENT comme la cible, avant d'appeler `arc_metrics.riegel` — les DEUX "
        "côtés de la comparaison sont ainsi en équivalent plat, jamais un mélange brut/converti qui "
        "compterait le relief deux fois. VDOT (tendance de VO2max, `metric_day.vo2max`) en repli si "
        "aucune référence dure n'est trouvée.\n\n"
        "Toutes les vitesses issues du modèle (personnel ET générique) sont multipliées par ce facteur "
        "avant d'en dériver les trois scénarios — la dispersion personnelle (IQR) est donc, elle aussi, "
        "mise à l'échelle de l'intensité de course, pas seulement le point central. Un facteur calculé "
        "sous 1.0 pour une course prédite de moins de `INTENSITY_CLAMP_DURATION_S` (4h30) est implausible "
        "(l'allure de course ne peut pas être plus lente que l'allure d'endurance sur une distance "
        "courte) et plafonné à 1.0, avec un avertissement — au-delà de ce seuil, l'exposant de Riegel en "
        "trail (1.15) prédit déjà, à raison, un ralentissement marqué sur un ultra, aucun plancher n'y "
        "est appliqué. Sans distance GPX exploitable, sans référence plate personnelle, ou sans "
        "référence dure/tendance VO2max exploitable, `intensity_factor` reste `1.0` et `intensity_source` "
        "vaut `\"none\"` — le plan reste alors EXPLICITEMENT une allure d'ENDURANCE (jamais une allure de "
        "course inventée), signalé en clair dans `warnings`."
    ),
    "fade": (
        "Le fade GAP médian des sorties longues récentes (`arc_durability`/`arc_index.durability_trend`, "
        "#48, fenêtre `--fade-weeks`, défaut 12 semaines glissantes) est appliqué comme un "
        "ralentissement PROGRESSIF sur la vitesse : nul sur le premier tiers de la distance totale de "
        "la course (même repère que la mesure source, qui compare premier et dernier tiers d'une sortie "
        "longue), puis une rampe LINÉAIRE jusqu'à l'arrivée. Calibrée pour que la MOYENNE du "
        "ralentissement sur le DERNIER TIERS égale exactement `fade_pct` (revue de code #59, should-fix) "
        "— une simple rampe de 0 à `fade_pct` à l'arrivée ne fait, en moyenne sur ce dernier tiers, que "
        "0,75 × `fade_pct` (aire d'un triangle) ; `FADE_LAST_THIRD_MEAN_FACTOR` (4/3) est le facteur qui "
        "rend cette moyenne exacte au ralentissement MESURÉ (`fade_pct` est LUI-MÊME défini par "
        "`arc_durability` comme une moyenne de dernier tiers, jamais une valeur ponctuelle à "
        "l'arrivée). `FADE_MIN_SPEED_FACTOR` (5 %) plafonne le ralentissement en toute circonstance — "
        "jamais une vitesse nulle ou négative pour un `fade_pct` extrême. Sans aucune sortie longue avec "
        "un fade GAP mesurable dans la fenêtre, un fade générique de repli est utilisé "
        "(`DEFAULT_GENERIC_FADE_PCT`, 5 %) — approximation du projet, PAS une mesure, toujours signalée "
        "(`fade_source: \"generic\"`). Le fade mesuré/générique est en outre ÉCHELONNÉ par la durée de "
        "course PRÉDITE (scénario réaliste, avant application du fade) face au seuil de sortie longue "
        "(`arc_metrics.LONG_RUN_MIN_DURATION_S`, 90 min, revue de code #59, should-fix) : appliquer "
        "PLEINEMENT un fade mesuré sur des sorties de plus de 90 minutes à une course de 30 minutes n'a "
        "aucune justification physiologique. `fade_pct_applied` (proportionnel à `durée prédite / 90 "
        "min`, plafonné à 1) est la valeur RÉELLEMENT appliquée ; `fade_pct` reste la valeur mesurée/"
        "générique brute, pour la transparence.\n\n"
        "**Neutre en temps total quand `intensity_source != \"none\"`** (2ᵉ revue de code #59, "
        "should-fix) : Riegel/VDOT prédisent déjà un temps de course qui intègre implicitement une "
        "dégradation d'endurance sur la distance (l'exposant de Riegel > 1, la courbe VDOT) — appliquer "
        "EN PLUS le fade GAP comme un ralentissement NET aurait compté cette dégradation deux fois, "
        "gonflant le temps total au-delà de ce que Riegel/VDOT prédisent déjà. Le fade est alors "
        "RENORMALISÉ après application (`_renormalize_fade_time_neutral`) : chaque scénario garde le "
        "MÊME total qu'un plan sans fade (plus rapide en début de course, plus lent en fin — la FORME "
        "reste utile pour le rythme à tenir), seule la RÉPARTITION dans le temps change, jamais le total. "
        "Quand `intensity_source == \"none\"` (allure d'endurance simple, aucune prédiction Riegel/VDOT "
        "sous-jacente), le fade reste un vrai ralentissement NET comme avant — rien à double-compter, "
        "l'allure de base n'intègre alors aucune dégradation implicite."
    ),
    "heat": (
        "Reprend TELS QUELS les seuils déjà documentés dans `agents/course-strategist.md` (ÉTAPE 6) — "
        "approximation du projet, jamais une source physiologique vérifiable pour ces pourcentages "
        "précis : température max prévue > 25 °C -> temps × 1.10, < 5 °C -> temps × 1.05, entre les "
        "deux -> aucun ajustement. Un supplément (`HEAT_UNACCLIMATED_EXTRA_FACTOR`, +5 %) s'applique "
        "en plus si la course est prévue chaude ET que l'athlète a eu moins de "
        "`HEAT_ACCLIMATION_MIN_HOT_SESSIONS` séances chaudes sur les 14 derniers jours "
        "(`arc_index.heat_acclimation_today`, #38) : un pari optimiste sur une acclimatation supposée "
        "serait plus dangereux qu'un plan trop prudent. Le facteur météo s'applique UNIFORMÉMENT à "
        "tous les segments (pas de section plus/moins exposée modélisée ici). Sans AUCUNE séance "
        "exploitable sur la fenêtre (`sessions_considered == 0`, revue de code #59, should-fix) — pas "
        "seulement sans séance chaude — l'acclimatation reste `None` (statut inconnu), jamais assimilée "
        "à une non-acclimatation : l'absence de donnée n'est pas une preuve d'exposition faible. "
        "L'acclimatation est évaluée sur les 14 jours précédant `--today` (ou la date du jour, par "
        "défaut) — jamais la date de la course elle-même, souvent bien plus tard."
    ),
    "aid_stations": (
        "Chaque ravitaillement ajoute un temps d'arrêt FIXE au cumul (`stop_s` de la station si fourni, "
        "sinon `DEFAULT_AID_STATION_STOP_S`, 90 s — approximation du projet, un ravito simple) — "
        "identique pour les trois scénarios (aucune donnée ne justifie un arrêt plus long pour un "
        "scénario plus lent). Un ravito situé au-delà de la fin mesurée du GPX (revue de code #59, "
        "should-fix — ex. tracé GPS coupé avant l'arrivée officielle) n'est jamais supprimé "
        "silencieusement : il est rattaché au temps d'ARRIVÉE (dernier cumul connu), avec une note "
        "explicite. `--official-distance-m` (optionnel) rééchelonne LINÉAIREMENT les `km` de "
        "ravitaillement fournis (supposés en km OFFICIELS de course) sur la distance RÉELLEMENT mesurée "
        "du GPX (`km_gpx = km_officiel × distance_gpx / distance_officielle`) — utile quand un tracé GPS "
        "mesure une distance légèrement différente de la distance officielle de course."
    ),
    "cutoffs": (
        "Une barrière horaire (`aid_station.cutoff`) accepte trois formats (revue de code #59, "
        "should-fix — l'ancien format HH:MM seul ne pouvait pas exprimer une barrière du surlendemain "
        "sur un ultra) : `HH:MM` (jour de course par défaut, ou `cutoff_day` explicite — 1 = jour du "
        "départ, 2 = lendemain, etc. ; SANS `cutoff_day`, une heure antérieure à l'heure de départ est "
        "supposée le LENDEMAIN, comportement historique conservé) ; `+HH:MM` élapsé depuis le départ "
        "(les heures peuvent dépasser 24, ex. `+30:00` pour un ultra) ; une date-heure ISO 8601 complète "
        "(`2026-11-16T10:30:00`) pour une barrière à une date/heure absolue sans ambiguïté. Comparée à "
        "l'heure de passage CUMULÉE de chaque scénario (départ + temps de segment + arrêts ravito). "
        "Marge = barrière − passage. `\"ok\"` si marge ≥ `CUTOFF_MARGIN_OK_S` (30 min — approximation du "
        "projet, pas une règle de course réelle), `\"tendu\"` si 0 ≤ marge < 30 min, `\"hors_delai\"` "
        "si marge < 0 (le scénario n'atteindrait pas la barrière)."
    ),
    "missing_elevation": (
        "Un point GPX sans `<ele>` produit une pente `None` pour les paires qui le touchent "
        "(`arc_elevation.grade_series`) — revue de code #59, blocant : prédire une vitesse `None` sur "
        "ces portions faisait tomber le temps de segment ENTIER à `None`, ignoré par `compute_passages` "
        "comme une contribution nulle (un GPX sans AUCUNE altitude rendait donc un plan à 0 seconde, "
        "`exit 0`, sans le moindre avertissement). Une pente `None` est maintenant traitée comme un "
        "PLAT explicite (grade 0) avec un `reason_code`/une note dédiés (`\"missing_elevation\"`) sur le "
        "segment concerné — `source` est TOUJOURS `\"generic\"` pour ces points (nit, revue de code #59) : "
        "ce n'est jamais une mesure de terrain réelle, dire `\"personal\"` (ce que le modèle rendrait pour "
        "une VRAIE pente plate) prétendrait à une confiance que l'absence d'altitude ne permet pas. ET un "
        "avertissement `warnings` au niveau du "
        "plan dès que la couverture d'altitude du GPX est incomplète (`< 99,5 %` des points) — un GPX "
        "SANS AUCUNE altitude déclenche un avertissement fort (parcours entier traité à plat, D+/D- "
        "inconnus). Le D+/D- total reste, lui, sous-estimé d'autant (aucune donnée pour le calculer) — "
        "l'avertissement le dit explicitement plutôt que de laisser un total plus petit se faire passer "
        "pour un vrai D+/D-."
    ),
    "provenance": (
        "`provenance_summary` rend la part de distance totale prédite par segment `personal`/"
        "`generic`/`mixed` (`arc_slope_model.predict_speed.source`, combinée par segment — un segment "
        "dont les points touchent plusieurs provenances est lui-même `\"mixed\"`) — le critère "
        "d'acceptation #59 (« le plan indique la provenance par segment ») est vérifiable directement "
        "sur `segments[].source`, ce résumé n'est qu'un agrégat pratique pour l'affichage."
    ),
}


# ---------------------------------------------------------------------------
# GPX -> points (duplication volontaire et minimale de
# `skills/gpx-analysis/scripts/analyze_gpx.parse_gpx`/`haversine` : le moteur
# racine ne doit jamais dépendre d'un script de skill, voir le docstring du
# module — sens de dépendance unique skill -> moteur, jamais l'inverse).
# ---------------------------------------------------------------------------

def parse_gpx(path: Path) -> List[dict]:
    """Extrait la liste ordonnée des points `{lat, lon, ele}` de TOUS les
    `trk`/`trkseg` du fichier, concaténés dans l'ordre du document (pas
    seulement le premier — un GPX à plusieurs segments/traces reste rare pour
    un parcours de course, mais rien ici ne le suppose)."""
    tree = ET.parse(path)
    root = tree.getroot()
    pts: List[dict] = []
    for trkpt in root.iter():
        tag = trkpt.tag.rsplit("}", 1)[-1]
        if tag != "trkpt":
            continue
        try:
            lat = float(trkpt.attrib["lat"])
            lon = float(trkpt.attrib["lon"])
        except (KeyError, ValueError):
            continue
        ele = None
        for child in trkpt:
            if child.tag.rsplit("}", 1)[-1] == "ele":
                try:
                    ele = float(child.text)
                except (TypeError, ValueError):
                    pass
        pts.append({"lat": lat, "lon": lon, "ele": ele})
    return pts


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en mètres entre deux points GPS (formule de Haversine)."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _cumulative_distances(pts: Sequence[dict]) -> List[float]:
    dist = [0.0]
    for i in range(1, len(pts)):
        dist.append(dist[-1] + haversine(pts[i - 1]["lat"], pts[i - 1]["lon"], pts[i]["lat"], pts[i]["lon"]))
    return dist


def elevation_coverage_pct(pts: Sequence[dict]) -> float:
    """Part (0-100) des points GPX porteurs d'une altitude — voir
    `ASSUMPTIONS["missing_elevation"]`. `100.0` pour une liste vide (rien à
    signaler)."""
    if not pts:
        return 100.0
    known = sum(1 for p in pts if p.get("ele") is not None)
    return known / len(pts) * 100.0


def course_totals(pts: Sequence[dict], *, smooth_taps: int = EL.DEFAULT_SMOOTH_TAPS) -> Tuple[float, float, float]:
    """Distance/D+/D- TOTAUX du GPX, calcul LÉGER (même lissage d'altitude que
    `segment_course`, mais sans segmentation) — utilisé par `main()` pour
    résoudre `intensity_factor` depuis les totaux du GPX RÉELLEMENT analysé,
    jamais depuis `planning/active_objective.md` (voir
    `ASSUMPTIONS["base_pace"]`, revue de code #59, BLOQUANT). `(0.0, 0.0, 0.0)`
    pour moins de 2 points."""
    if len(pts) < 2:
        return 0.0, 0.0, 0.0
    dist = _cumulative_distances(pts)
    ele_smooth = EL.smooth_moving_average([p.get("ele") for p in pts], smooth_taps)
    gain = loss = 0.0
    for k in range(1, len(pts)):
        a, b = ele_smooth[k - 1], ele_smooth[k]
        if a is None or b is None:
            continue
        d = b - a
        if d > 0:
            gain += d
        else:
            loss += -d
    return dist[-1], gain, loss


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

def _weighted_mean(values: Sequence[Optional[float]], weights: Sequence[float]) -> Optional[float]:
    pairs = [(v, w) for v, w in zip(values, weights) if v is not None and w > 0]
    if not pairs:
        return None
    total_w = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / total_w


def _profile_for(dist: Sequence[float], grades: Sequence[Optional[float]],
                  i_start: int, i_end: int) -> List[Tuple[float, Optional[float]]]:
    """Profil `[(dx_m, grade), ...]` pour chaque paire de points consécutifs de
    `[i_start, i_end]` — consommé par `predict_segments` pour intégrer `Δd /
    v(pente locale)` (voir `ASSUMPTIONS["rolling_terrain"]`). `grade` est la
    moyenne des pentes des deux points de la paire (déjà lissées par
    `arc_elevation.grade_series`), l'une ou l'autre si une seule est connue,
    `None` si aucune (altitude manquante des deux côtés — voir
    `ASSUMPTIONS["missing_elevation"]`)."""
    profile: List[Tuple[float, Optional[float]]] = []
    for k in range(i_start + 1, i_end + 1):
        dx = dist[k] - dist[k - 1]
        if dx <= 0:
            continue
        g_a, g_b = grades[k - 1], grades[k]
        if g_a is not None and g_b is not None:
            g = (g_a + g_b) / 2.0
        elif g_a is not None:
            g = g_a
        elif g_b is not None:
            g = g_b
        else:
            g = None
        profile.append((dx, g))
    return profile


def _raw_segment(dist: Sequence[float], grades: Sequence[Optional[float]],
                  ele_smooth: Sequence[Optional[float]], i_start: int, i_end: int) -> dict:
    """Segment brut sur les indices [i_start, i_end] (inclusifs), AVANT fusion."""
    idx = list(range(i_start, i_end + 1))
    seg_weights = []
    for k in idx:
        prev = max(i_start, k - 1)
        seg_weights.append(max(0.0, dist[k] - dist[prev]) if k > i_start else 0.0)
    grade_mean = _weighted_mean([grades[k] for k in idx], [max(w, 1e-6) for w in seg_weights] or [1.0])
    gain = loss = 0.0
    for k in range(i_start + 1, i_end + 1):
        a, b = ele_smooth[k - 1], ele_smooth[k]
        if a is None or b is None:
            continue
        d = b - a
        if d > 0:
            gain += d
        else:
            loss += -d
    return {
        "i_start": i_start, "i_end": i_end,
        "km_start": round(dist[i_start] / 1000.0, 3),
        "km_end": round(dist[i_end] / 1000.0, 3),
        "distance_m": round(dist[i_end] - dist[i_start], 1),
        "grade_mean_pct": round(grade_mean * 100.0, 2) if grade_mean is not None else None,
        "elevation_gain_m": round(gain, 1),
        "elevation_loss_m": round(loss, 1),
        "_profile": _profile_for(dist, grades, i_start, i_end),
    }


def _merge_raw(a: dict, dist: Sequence[float], grades: Sequence[Optional[float]],
               ele_smooth: Sequence[Optional[float]], b: dict) -> dict:
    return _raw_segment(dist, grades, ele_smooth, a["i_start"], b["i_end"])


def segment_course(pts: Sequence[dict], *, target_segment_m: float = DEFAULT_SEGMENT_M,
                    min_segment_m: float = MIN_SEGMENT_M,
                    max_segment_factor: float = MAX_SEGMENT_FACTOR,
                    merge_grade_delta_pct: float = MERGE_GRADE_DELTA_PCT,
                    window_m: float = EL.DEFAULT_GRADE_WINDOW_M,
                    smooth_taps: int = EL.DEFAULT_SMOOTH_TAPS) -> List[dict]:
    """Découpe un parcours GPX (points `{lat, lon, ele}`, déjà parsés par
    `parse_gpx`) en segments de longueur cible fusionnés par pente similaire —
    voir `ASSUMPTIONS["segmentation"]` pour la méthode complète. Rend une liste
    VIDE si moins de 2 points exploitables (rien à segmenter).

    Chaque segment porte les champs PUBLICS du contrat (`id`, `km_start`,
    `km_end`, `distance_m`, `grade_mean_pct` — signé, `None` si non calculable
    sur tout le segment —, `elevation_gain_m`, `elevation_loss_m`) PLUS une clé
    privée `_profile` (voir `_profile_for`), consommée par `predict_segments`
    et jamais émise dans le JSON final du plan."""
    if len(pts) < 2:
        return []
    dist = _cumulative_distances(pts)
    raw_ele = [p.get("ele") for p in pts]
    ele_smooth = EL.smooth_moving_average(raw_ele, smooth_taps)
    samples = [{"t_s": float(i), "distance_m": dist[i], "altitude_m": raw_ele[i]} for i in range(len(pts))]
    graded = EL.grade_series(samples, window_m=window_m, smooth_taps=smooth_taps)
    grades = [s["grade"] for s in graded]  # aligné : grade_series trie par t_s, déjà croissant ici

    n = len(pts)
    total_m = dist[-1]
    if total_m <= 0:
        return []

    # 1) Découpage brut en tranches de distance ~cible.
    raws: List[dict] = []
    i_start = 0
    next_boundary = target_segment_m
    for i in range(1, n):
        if dist[i] >= next_boundary or i == n - 1:
            raws.append(_raw_segment(dist, grades, ele_smooth, i_start, i))
            i_start = i
            next_boundary = dist[i] + target_segment_m
            if i == n - 1:
                break
    if not raws:
        raws = [_raw_segment(dist, grades, ele_smooth, 0, n - 1)]

    # 2) Fusion greedy des segments adjacents de pente similaire, plafonnée en
    # longueur (voir ASSUMPTIONS["segmentation"]) — couvre maintenant aussi le
    # DERNIER segment (revue de code #59 : l'ancienne fusion inconditionnelle
    # du reliquat final, avant cette passe, ignorait la pente).
    max_segment_m = target_segment_m * max_segment_factor
    merged: List[dict] = []
    for seg in raws:
        if merged:
            prev = merged[-1]
            prev_grade, seg_grade = prev["grade_mean_pct"], seg["grade_mean_pct"]
            combined_len = prev["distance_m"] + seg["distance_m"]
            similar = (prev_grade is not None and seg_grade is not None
                       and abs(prev_grade - seg_grade) <= merge_grade_delta_pct)
            if similar and combined_len <= max_segment_m:
                merged[-1] = _merge_raw(prev, dist, grades, ele_smooth, seg)
                continue
        merged.append(dict(seg))

    # 3) Dernier recours (revue de code #59) : un reliquat encore trop court
    # APRÈS la fusion par pente (terrain trop varié pour fusionner « proprement »)
    # est fusionné dans le précédent quelle que soit sa pente — jamais un
    # segment orphelin de quelques mètres.
    if len(merged) > 1 and merged[-1]["distance_m"] < min_segment_m:
        merged[-2] = _merge_raw(merged[-2], dist, grades, ele_smooth, merged[-1])
        merged.pop()

    width = max(2, len(str(len(merged))))
    out = []
    for i, seg in enumerate(merged, start=1):
        out.append({
            "id": f"s{i:0{width}d}",
            "km_start": seg["km_start"],
            "km_end": seg["km_end"],
            "distance_m": seg["distance_m"],
            "grade_mean_pct": seg["grade_mean_pct"],
            "elevation_gain_m": seg["elevation_gain_m"],
            "elevation_loss_m": seg["elevation_loss_m"],
            "_profile": seg["_profile"],
        })
    return out


# ---------------------------------------------------------------------------
# Prédiction par segment
# ---------------------------------------------------------------------------

# Panier CENTRAL du modèle (celui qui contient la pente 0, `arc_slope_model.GRADE_BINS`)
# — repli de `_snap_grade_to_bin` (voir `ASSUMPTIONS["rolling_terrain"]`) pour
# un `bins` de test sans `grade_lo`/`grade_hi`.
_CENTER_BIN_LO, _CENTER_BIN_HI = next((lo, hi) for lo, hi, _ in SL.GRADE_BINS if lo <= 0.0 < hi)


def _snap_grade_to_bin(grade: Optional[float], bins: Sequence[dict]) -> Optional[float]:
    """Neutralise l'interpolation de `predict_speed` pour une pente qui tombe
    dans l'intervalle `[lo, hi)` d'un panier PERSONNEL de `bins` — voir
    `ASSUMPTIONS["rolling_terrain"]` (2ᵉ revue de code #59, should-fix). Rend
    exactement le point milieu de ce panier, jamais la pente brute. Un panier
    sans `grade_lo`/`grade_hi` (clés absentes — fixtures de test à un seul
    point) est IGNORÉ pour cette recherche, jamais traité comme couvrant
    `[-inf, +inf)` (ce que renverrait `dict.get` par défaut). Repli, si aucun
    panier personnel ne couvre `grade` : neutralise seulement le panier
    CENTRAL canonique du modèle (`_CENTER_BIN_LO`/`_CENTER_BIN_HI`)."""
    if grade is None:
        return None
    for b in bins:
        if b.get("source") != "personal" or "grade_lo" not in b or "grade_hi" not in b:
            continue
        lo = b["grade_lo"] if b["grade_lo"] is not None else float("-inf")
        hi = b["grade_hi"] if b["grade_hi"] is not None else float("inf")
        if lo <= grade < hi:
            return b["grade_mid"]
    if _CENTER_BIN_LO <= grade < _CENTER_BIN_HI:
        return 0.0
    return grade


def fade_speed_multiplier(km_frac: float, fade_pct: float) -> float:
    """Multiplicateur de vitesse (<= 1.0, jamais sous `FADE_MIN_SPEED_FACTOR`)
    au point `km_frac` (0-1, fraction de la distance totale de course) pour un
    fade GAP `fade_pct` (%) mesuré entre premier et dernier tiers d'une sortie
    longue — voir `ASSUMPTIONS["fade"]` pour la calibration complète (rampe
    linéaire à partir du premier tiers, `FADE_LAST_THIRD_MEAN_FACTOR` pour que
    la MOYENNE du dernier tiers égale exactement `fade_pct`)."""
    if fade_pct <= 0 or km_frac <= 1.0 / 3.0:
        return 1.0
    t = min(1.0, (km_frac - 1.0 / 3.0) / (2.0 / 3.0))
    reduction = t * FADE_LAST_THIRD_MEAN_FACTOR * (fade_pct / 100.0)
    return max(FADE_MIN_SPEED_FACTOR, 1.0 - reduction)


def scale_fade_to_duration(fade_pct: float, predicted_duration_s: Optional[float]) -> float:
    """Échelonne un `fade_pct` mesuré/générique sur SORTIE LONGUE
    (`arc_metrics.LONG_RUN_MIN_DURATION_S`, 90 min) à la durée RÉELLE de la
    course prédite — voir `ASSUMPTIONS["fade"]`. `predicted_duration_s`
    inconnu (`None`) laisse `fade_pct` inchangé (rien à échelonner sans une
    estimation de durée)."""
    if fade_pct <= 0 or predicted_duration_s is None:
        return fade_pct
    scale = min(1.0, max(0.0, predicted_duration_s / M.LONG_RUN_MIN_DURATION_S))
    return fade_pct * scale


def heat_time_factor(temp_max_c: Optional[float], *, acclimated: Optional[bool] = None) -> Tuple[float, List[str]]:
    """Facteur multiplicatif sur le TEMPS (>= 1.0) pour la météo prévue — voir
    `ASSUMPTIONS["heat"]`. `acclimated=False` ajoute le supplément
    `HEAT_UNACCLIMATED_EXTRA_FACTOR` si `temp_max_c` dépasse `HEAT_HOT_C`.
    Rend `(facteur, notes)`."""
    if temp_max_c is None:
        return 1.0, ["aucune prévision météo fournie : aucun ajustement chaleur/froid appliqué"]
    notes = []
    factor = 1.0
    if temp_max_c > HEAT_HOT_C:
        factor *= HEAT_HOT_TIME_FACTOR
        notes.append(f"chaleur prévue ({temp_max_c:g} °C > {HEAT_HOT_C:g} °C) : temps × {HEAT_HOT_TIME_FACTOR:g} "
                     "(approximation du projet)")
        if acclimated is False:
            factor *= HEAT_UNACCLIMATED_EXTRA_FACTOR
            notes.append(f"faible acclimatation chaleur récente (#38) : supplément × "
                         f"{HEAT_UNACCLIMATED_EXTRA_FACTOR:g} (approximation du projet, évaluée sur les 14 "
                         "jours précédant --today)")
    elif temp_max_c < HEAT_COLD_C:
        factor *= HEAT_COLD_TIME_FACTOR
        notes.append(f"froid prévu ({temp_max_c:g} °C < {HEAT_COLD_C:g} °C) : temps × {HEAT_COLD_TIME_FACTOR:g} "
                     "(approximation du projet)")
    return factor, notes


def _scale_prediction_speeds(prediction: dict, factor: float) -> dict:
    """Multiplie les vitesses d'une prédiction (`speed_ms`/`ci_low_speed_ms`/
    `ci_high_speed_ms`) par `factor` (`intensity_factor`, voir
    `ASSUMPTIONS["base_pace"]`) — `source`/`reason_code` inchangés (la
    provenance ne dépend pas de l'intensité, seule la vitesse est mise à
    l'échelle)."""
    if factor == 1.0:
        return prediction
    scaled = dict(prediction)
    for key in ("speed_ms", "ci_low_speed_ms", "ci_high_speed_ms"):
        if scaled.get(key) is not None:
            scaled[key] = scaled[key] * factor
    return scaled


def _scenario_speeds(prediction: dict) -> Dict[str, Optional[float]]:
    """Vitesse par scénario — voir `ASSUMPTIONS["scenarios"]` pour l'écart
    PLANCHER appliqué à une dispersion personnelle mesurée trop étroite."""
    speed = prediction.get("speed_ms")
    if speed is None:
        return {s: None for s in SCENARIOS}
    ci_low, ci_high = prediction.get("ci_low_speed_ms"), prediction.get("ci_high_speed_ms")
    if ci_low is not None and ci_high is not None:
        safe_speed = min(ci_low, speed * GENERIC_SCENARIO_SPEED_FACTOR["safe"])
        ambitious_speed = max(ci_high, speed * GENERIC_SCENARIO_SPEED_FACTOR["ambitious"])
        return {"safe": safe_speed, "realistic": speed, "ambitious": ambitious_speed}
    return {s: speed * GENERIC_SCENARIO_SPEED_FACTOR[s] for s in SCENARIOS}


def _segment_intervals(seg: dict) -> List[Tuple[float, Optional[float]]]:
    """Sous-intervalles `(dx_m, grade)` à intégrer pour ce segment — un segment
    RÉEL (`segment_course`) porte `_profile` (une entrée par paire de points
    GPX) ; un segment construit à la main (tests, pas de GPX) retombe sur UN
    SEUL intervalle couvrant `distance_m` à `grade_mean_pct` — mathématiquement
    équivalent au calcul par pente unique quand la pente est réellement
    uniforme sur tout le segment."""
    profile = seg.get("_profile")
    if profile:
        return profile
    grade = seg["grade_mean_pct"] / 100.0 if seg.get("grade_mean_pct") is not None else None
    return [(seg.get("distance_m") or 0.0, grade)]


def _combine_sources(sources: Sequence[Optional[str]]) -> Optional[str]:
    """Provenance représentative d'un segment à partir de la provenance de
    CHACUN de ses intervalles — `None` si aucun intervalle n'a de provenance,
    la provenance commune si tous s'accordent, `"mixed"` sinon (même sémantique
    que `arc_slope_model.predict_speed` pour un point isolé, étendue au
    segment)."""
    uniq = {s for s in sources if s is not None}
    if not uniq:
        return None
    if len(uniq) == 1:
        return next(iter(uniq))
    return "mixed"


def predict_segments(segments: Sequence[dict], bins: Sequence[dict], *,
                      fade_pct: float = 0.0, heat_factor: float = 1.0,
                      intensity_factor: float = 1.0) -> List[dict]:
    """Augmente chaque segment (`segment_course`) d'une prédiction de temps par
    scénario — pure, aucun accès disque. `bins` : `model["bins"]` d'un rapport
    `arc_slope_model.fit_slope_model`/`arc_index.slope_model_report`.

    Intègre `Δd / v(pente locale)` sur chaque sous-intervalle du segment (voir
    `ASSUMPTIONS["rolling_terrain"]`) plutôt que de prédire une seule fois sur
    la pente moyenne — jamais la même approximation pour un vrai plat et un
    profil vallonné à moyenne nulle. Une pente manquante (altitude GPX
    absente) est traitée comme un plat explicite, jamais une prédiction
    `None` silencieuse (voir `ASSUMPTIONS["missing_elevation"]`).

    Rend une COPIE des segments (champs publics uniquement — `_profile` et
    tout champ interne ne sont jamais réémis), chacun augmenté de `source`,
    `reason_code` (informationnel, ex. `"extrapolated"`/`"missing_elevation"`/
    `"no_model"`), `predicted_time_s` (objet par scénario, secondes entières —
    voir `SEGMENT_ROUND_S`), `pace_s_km` (objet par scénario), `notes` (liste
    de courtes explications)."""
    total_m = sum(seg["distance_m"] for seg in segments) or 1.0
    cum_m = 0.0
    out = []
    for seg in segments:
        intervals = _segment_intervals(seg)
        seg_total_m = sum(dx for dx, _ in intervals) or seg.get("distance_m") or 0.0

        time_acc: Dict[str, float] = {s: 0.0 for s in SCENARIOS}
        has_speed: Dict[str, bool] = {s: False for s in SCENARIOS}
        sources: List[Optional[str]] = []
        reason_codes: Set[str] = set()
        missing_elevation_m = 0.0
        cum_local = 0.0

        for dx, grade in intervals:
            if dx <= 0:
                continue
            point_frac = (cum_m + cum_local + dx / 2.0) / total_m
            cum_local += dx

            if grade is None:
                missing_elevation_m += dx
                query_grade = 0.0
                reason_codes.add("missing_elevation")
            else:
                query_grade = grade

            prediction = SL.predict_speed(_snap_grade_to_bin(query_grade, bins), bins)
            prediction = _scale_prediction_speeds(prediction, intensity_factor)
            if grade is None:
                # Altitude manquante (nit, revue de code #59) : jamais `"personal"`
                # (ce que le modèle rendrait pour une VRAIE pente plate mesurée) —
                # cette pente est SUPPOSÉE, pas mesurée, `"generic"` quelle que soit
                # la provenance que `predict_speed` rendrait pour 0 %.
                sources.append("generic" if prediction.get("speed_ms") is not None else None)
            else:
                sources.append(prediction.get("source"))
                if prediction.get("reason_code"):
                    reason_codes.add(prediction["reason_code"])

            fade_mult = fade_speed_multiplier(point_frac, fade_pct)
            for scenario, base_speed in _scenario_speeds(prediction).items():
                if base_speed is None or base_speed <= 0:
                    continue
                effective_speed = base_speed * fade_mult / heat_factor
                if effective_speed <= 0:
                    continue
                time_acc[scenario] += dx / effective_speed
                has_speed[scenario] = True

        cum_m += seg_total_m

        if reason_codes - {"missing_elevation"} and "no_model" in reason_codes:
            reason_code = "no_model"
        elif "extrapolated" in reason_codes:
            reason_code = "extrapolated"
        elif "missing_elevation" in reason_codes:
            reason_code = "missing_elevation"
        elif not has_speed["realistic"]:
            reason_code = "no_model"
        else:
            reason_code = None

        notes = []
        if reason_code == "no_model":
            notes.append("aucun modèle personnel disponible : ce segment ne peut pas être prédit")
        if reason_code == "extrapolated" or "extrapolated" in reason_codes:
            notes.append("pente hors plage du modèle personnel : vitesse prolongée à plat (extrapolation)")
        if missing_elevation_m > 0:
            notes.append(
                f"altitude manquante sur {round(missing_elevation_m)} m de ce segment : pente supposée "
                "nulle (plat)")

        predicted_time_s = {
            s: (int(round(time_acc[s] / SEGMENT_ROUND_S)) * SEGMENT_ROUND_S if has_speed[s] else None)
            for s in SCENARIOS
        }
        pace_s_km = {
            s: (round(1000.0 * time_acc[s] / seg_total_m, 1) if has_speed[s] and seg_total_m > 0 else None)
            for s in SCENARIOS
        }

        out.append({
            "id": seg["id"], "km_start": seg["km_start"], "km_end": seg["km_end"],
            "distance_m": seg["distance_m"], "grade_mean_pct": seg["grade_mean_pct"],
            "elevation_gain_m": seg["elevation_gain_m"], "elevation_loss_m": seg["elevation_loss_m"],
            "source": _combine_sources(sources), "reason_code": reason_code,
            "predicted_time_s": predicted_time_s, "pace_s_km": pace_s_km, "notes": notes,
        })
    return out


def provenance_summary(segments: Sequence[dict]) -> dict:
    """Part de distance totale par provenance (`ASSUMPTIONS["provenance"]`)."""
    total_m = sum(seg["distance_m"] for seg in segments)
    shares: Dict[str, float] = {}
    if total_m <= 0:
        return {"personal_pct": None, "generic_pct": None, "mixed_pct": None, "unknown_pct": None}
    for seg in segments:
        key = seg.get("source") or "unknown"
        shares[key] = shares.get(key, 0.0) + seg["distance_m"]
    return {
        f"{key}_pct": round(dist_m / total_m * 100.0, 1)
        for key, dist_m in {**{"personal": 0.0, "generic": 0.0, "mixed": 0.0, "unknown": 0.0}, **shares}.items()
    }


# ---------------------------------------------------------------------------
# Ravitaillements, temps de passage, barrières
# ---------------------------------------------------------------------------

def rescale_aid_stations(aid_stations: Sequence[dict], measured_total_m: Optional[float],
                          official_distance_m: Optional[float]) -> List[dict]:
    """Rééchelonne les `km` de ravitaillement (supposés en km OFFICIELS de
    course) sur la distance RÉELLEMENT mesurée du GPX — voir
    `ASSUMPTIONS["aid_stations"]`. Rend `aid_stations` inchangé si l'une des
    deux distances manque."""
    if not official_distance_m or official_distance_m <= 0 or not measured_total_m:
        return list(aid_stations)
    ratio = measured_total_m / official_distance_m
    out = []
    for station in aid_stations:
        rescaled = dict(station)
        rescaled["km"] = round(rescaled["km"] * ratio, 3)
        out.append(rescaled)
    return out


def compute_passages(segments: Sequence[dict], aid_stations: Sequence[dict]) -> dict:
    """Temps de passage cumulés par scénario à la fin de CHAQUE segment, plus
    les arrêts ravito (voir `ASSUMPTIONS["aid_stations"]`). Rend
    `{"segment_passages": [...], "totals_s": {...}, "aid_station_passages": [...]}`,
    tous les temps cumulés arrondis à la MINUTE (`PASSAGE_ROUND_S`).

    `segment_passages[i]` : `{"segment_id", "km_end", scenario: cumulative_s}`
    (cumul APRÈS le segment, arrêts ravito déjà traversés compris).
    `aid_station_passages` : une entrée par station fournie, avec le temps
    cumulé d'ARRIVÉE à la station (avant son propre arrêt) par scénario — une
    station au-delà de la fin mesurée du GPX est rattachée au temps
    d'ARRIVÉE, avec une `note` explicite (jamais supprimée silencieusement)."""
    cum = {s: 0.0 for s in SCENARIOS}
    segment_passages = []
    aid_idx = 0
    aid_sorted = sorted(aid_stations, key=lambda a: a["km"])
    aid_station_passages = []
    last_km_end = segments[-1]["km_end"] if segments else 0.0
    for seg in segments:
        for scenario in SCENARIOS:
            t = seg["predicted_time_s"].get(scenario)
            if t is not None:
                cum[scenario] += t
        segment_passages.append(
            {"segment_id": seg["id"], "km_end": seg["km_end"],
             **{s: _round_passage(cum[s]) for s in SCENARIOS}})
        while aid_idx < len(aid_sorted) and aid_sorted[aid_idx]["km"] <= seg["km_end"]:
            station = aid_sorted[aid_idx]
            aid_station_passages.append({
                "km": station["km"], "name": station.get("name"),
                **{s: _round_passage(cum[s]) for s in SCENARIOS},
            })
            stop_s = station.get("stop_s", DEFAULT_AID_STATION_STOP_S)
            for scenario in SCENARIOS:
                cum[scenario] += stop_s
            aid_idx += 1
    # Ravitos au-delà de la fin mesurée du GPX (revue de code #59, should-fix) :
    # rattachés à l'arrivée plutôt que silencieusement perdus.
    while aid_idx < len(aid_sorted):
        station = aid_sorted[aid_idx]
        entry = {
            "km": station["km"], "name": station.get("name"),
            **{s: _round_passage(cum[s]) for s in SCENARIOS},
            "note": (f"ravito au km {station['km']:g} au-delà de la fin mesurée du GPX "
                     f"({last_km_end:g} km) : rattaché au temps d'arrivée"),
        }
        aid_station_passages.append(entry)
        stop_s = station.get("stop_s", DEFAULT_AID_STATION_STOP_S)
        for scenario in SCENARIOS:
            cum[scenario] += stop_s
        aid_idx += 1
    totals_s = {s: _round_passage(cum[s]) for s in SCENARIOS}
    return {"segment_passages": segment_passages, "totals_s": totals_s, "aid_station_passages": aid_station_passages}


def _parse_hhmm(value: str, *, label: str) -> Tuple[int, int]:
    """`HH:MM` strict (0-23:0-59) — lève `ValueError` (message nommant `label`)
    plutôt que de retomber silencieusement sur une heure par défaut (revue de
    code #59, nit : une heure de départ invalide passait inaperçue)."""
    try:
        hh_s, mm_s = value.split(":")
        hh, mm = int(hh_s), int(mm_s)
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{label} : heure HH:MM attendue (00:00-23:59), « {value} » reçu.") from exc
    return hh, mm


def _parse_cutoff_dt(cutoff: Optional[str], cutoff_day: Optional[int], start_dt: datetime) -> Optional[datetime]:
    """Résout une barrière horaire en date-heure absolue — voir
    `ASSUMPTIONS["cutoffs"]` pour les trois formats acceptés (`HH:MM`
    [+ `cutoff_day` optionnel], `+HH:MM` élapsé, date-heure ISO 8601). Rend
    `None` si `cutoff` est absent ou illisible (jamais une exception : une
    barrière mal formée ne doit pas faire échouer tout le plan)."""
    if not cutoff:
        return None
    text = cutoff.strip()
    if text.startswith("+"):
        try:
            hh_s, mm_s = text[1:].split(":")
            return start_dt + timedelta(hours=int(hh_s), minutes=int(mm_s))
        except ValueError:
            return None
    if "T" in text:
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    try:
        hh, mm = _parse_hhmm(text, label="aid_station.cutoff")
    except ValueError:
        return None
    day_offset = (cutoff_day - 1) if cutoff_day else 0
    cutoff_dt = (start_dt + timedelta(days=day_offset)).replace(hour=hh, minute=mm, second=0, microsecond=0)
    if not cutoff_day and cutoff_dt < start_dt:
        cutoff_dt += timedelta(days=1)
    return cutoff_dt


def check_cutoffs(aid_station_passages: Sequence[dict], aid_stations: Sequence[dict],
                   start_dt: datetime) -> List[dict]:
    """Marge de chaque scénario face à une barrière horaire — voir
    `ASSUMPTIONS["cutoffs"]`. Une station sans `cutoff` (ou dont le `cutoff`
    est illisible) n'apparaît pas dans le résultat (rien à vérifier)."""
    by_km = {round(a["km"], 6): a for a in aid_stations if a.get("cutoff")}
    out = []
    for passage in aid_station_passages:
        station = by_km.get(round(passage["km"], 6))
        if station is None:
            continue
        cutoff_dt = _parse_cutoff_dt(station.get("cutoff"), station.get("cutoff_day"), start_dt)
        if cutoff_dt is None:
            continue
        entry = {"km": passage["km"], "name": passage.get("name"), "cutoff": station["cutoff"]}
        for scenario in SCENARIOS:
            passage_dt = start_dt + timedelta(seconds=passage[scenario])
            margin_s = round((cutoff_dt - passage_dt).total_seconds())
            status = "ok" if margin_s >= CUTOFF_MARGIN_OK_S else ("tendu" if margin_s >= 0 else "hors_delai")
            entry[scenario] = {"margin_s": margin_s, "status": status}
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Orchestration pure (assemblage complet, sans accès disque)
# ---------------------------------------------------------------------------

def _renormalize_fade_time_neutral(segments: Sequence[dict], provisional_totals: Dict[str, Optional[float]]) -> Tuple[List[dict], Optional[str]]:
    """Rend le fade NEUTRE en temps total (voir `ASSUMPTIONS["fade"]`, 2ᵉ revue
    de code #59, should-fix) : Riegel/VDOT prédisent déjà une dégradation
    d'endurance sur la distance, le fade ne doit alors PAS s'ajouter par-dessus
    en NET, seulement redistribuer le MÊME temps total dans la course (plus
    rapide en début, plus lent en fin). `provisional_totals` : totaux par
    scénario d'une prédiction SANS fade (même `intensity_factor`/`heat_factor`)
    — la cible que le total AVEC fade doit retrouver après renormalisation.
    Rend `(segments, note)` — `note` est `None` si rien n'a changé (aucun total
    provisoire exploitable, ou fade déjà neutre)."""
    faded_totals = {
        s: (sum(seg["predicted_time_s"][s] for seg in segments if seg["predicted_time_s"][s] is not None) or None)
        for s in SCENARIOS
    }
    ratios = {}
    for s in SCENARIOS:
        prov, faded = provisional_totals.get(s), faded_totals.get(s)
        ratios[s] = (prov / faded) if prov and faded else 1.0
    if all(abs(r - 1.0) < 1e-9 for r in ratios.values()):
        return list(segments), None

    out = []
    for seg in segments:
        new_time: Dict[str, Optional[float]] = {}
        new_pace: Dict[str, Optional[float]] = {}
        for s in SCENARIOS:
            t = seg["predicted_time_s"][s]
            if t is None:
                new_time[s], new_pace[s] = None, None
                continue
            scaled_t = t * ratios[s]
            new_time[s] = int(round(scaled_t))
            new_pace[s] = round(1000.0 * scaled_t / seg["distance_m"], 1) if seg["distance_m"] else None
        out.append({**seg, "predicted_time_s": new_time, "pace_s_km": new_pace})

    note = (
        "fade rendu neutre en temps total (revue de code #59, should-fix) : la prédiction de temps de "
        "course (Riegel/VDOT) intègre déjà une dégradation d'endurance sur la distance — le fade "
        "redistribue ce même temps total (plus rapide en début de course, plus lent en fin) au lieu de "
        "s'ajouter par-dessus la prédiction.")
    return out, note


def build_race_plan(pts: Sequence[dict], bins: Sequence[dict], *,
                     aid_stations: Optional[Sequence[dict]] = None,
                     fade_pct: float = 0.0, fade_source: str = "generic",
                     temp_max_c: Optional[float] = None, acclimated: Optional[bool] = None,
                     acclimation_note: Optional[str] = None,
                     intensity_factor: float = 1.0, intensity_source: str = "none",
                     intensity_notes: Optional[Sequence[str]] = None,
                     flat_reference_speed_ms: Optional[float] = None, band: str = DEFAULT_BAND,
                     official_distance_m: Optional[float] = None,
                     start_time: str = "07:00", race_date: Optional[str] = None,
                     segment_m: float = DEFAULT_SEGMENT_M) -> dict:
    """Assemble le plan de course complet — pure (aucun accès disque), pour que
    la CLI et les tests partagent exactement le même chemin de calcul.

    Lève `ValueError` si `start_time` n'est pas un `HH:MM` valide (revue de
    code #59, nit : jamais un repli silencieux sur 07:00)."""
    hh, mm = _parse_hhmm(start_time, label="--start")
    base_date = date.fromisoformat(race_date) if race_date else date.today()
    start_dt = datetime(base_date.year, base_date.month, base_date.day, hh, mm)

    warnings: List[str] = []
    coverage = elevation_coverage_pct(pts)
    if coverage <= 0.0:
        warnings.append(
            "Aucune altitude dans le fichier GPX : le parcours entier est traité à plat (pente 0 "
            "partout), D+/D- et allures ne reflètent aucun relief réel — voir "
            "ASSUMPTIONS['missing_elevation'].")
    elif coverage < 99.5:
        warnings.append(
            f"Altitude manquante sur environ {100 - coverage:.0f} % des points du GPX : les segments "
            "concernés sont traités à plat (voir la note de chaque segment), le D+/D- total est "
            "sous-estimé d'autant.")
    if intensity_source == "none":
        warnings.append(
            "Aucune prédiction de temps de course exploitable (distance GPX, référence dure récente ou "
            "tendance VO2max manquants) : les allures reflètent l'allure D'ENDURANCE mesurée à "
            "l'entraînement, PAS l'allure de course visée — voir ASSUMPTIONS['base_pace'].")
    warnings.extend(intensity_notes or [])

    aid_stations = list(aid_stations or [])
    raw_segments = segment_course(pts, target_segment_m=segment_m)
    total_measured_m = raw_segments[-1]["km_end"] * 1000.0 if raw_segments else None
    aid_stations = rescale_aid_stations(aid_stations, total_measured_m, official_distance_m)

    heat_factor, heat_notes = heat_time_factor(temp_max_c, acclimated=acclimated)
    if acclimation_note:
        heat_notes = [*heat_notes, acclimation_note]

    # Passe préliminaire SANS fade (le facteur de fade dépend de la durée totale
    # PRÉDITE de la course, voir ASSUMPTIONS["fade"]) pour échelonner un fade
    # mesuré sur sortie longue à une course bien plus courte, ET pour disposer
    # d'un total DE RÉFÉRENCE par scénario (renormalisation "fade neutre",
    # voir `_renormalize_fade_time_neutral`).
    provisional = predict_segments(raw_segments, bins, fade_pct=0.0, heat_factor=heat_factor,
                                    intensity_factor=intensity_factor)
    provisional_totals = {
        s: (sum(seg["predicted_time_s"][s] for seg in provisional if seg["predicted_time_s"][s] is not None)
            or None)
        for s in SCENARIOS
    }
    predicted_duration_s = provisional_totals["realistic"]
    fade_pct_applied = scale_fade_to_duration(fade_pct, predicted_duration_s)
    fade_notes = []
    if fade_pct > 0 and fade_pct_applied < fade_pct - 1e-9:
        fade_notes.append(
            f"course prédite ≈ {round(predicted_duration_s / 60.0)} min, sous le seuil de sortie longue "
            f"(90 min, arc_metrics.LONG_RUN_MIN_DURATION_S) : fade réduit à {fade_pct_applied:.1f} % "
            f"(mesuré/générique : {fade_pct:.1f} %)")

    segments = predict_segments(raw_segments, bins, fade_pct=fade_pct_applied, heat_factor=heat_factor,
                                 intensity_factor=intensity_factor)

    # Fade rendu NEUTRE en temps total dès qu'une prédiction Riegel/VDOT sous-jacente
    # existe (voir ASSUMPTIONS["fade"]) : elle intègre déjà une dégradation d'endurance
    # sur la distance, l'ajouter EN PLUS aurait compté la fatigue deux fois.
    if intensity_source != "none":
        segments, renorm_note = _renormalize_fade_time_neutral(segments, provisional_totals)
        if renorm_note:
            fade_notes.append(renorm_note)

    passages = compute_passages(segments, aid_stations)
    cutoffs = check_cutoffs(passages["aid_station_passages"], aid_stations, start_dt)
    for aid_passage in passages["aid_station_passages"]:
        if aid_passage.get("note"):
            warnings.append(aid_passage["note"])

    total_distance_m = sum(seg["distance_m"] for seg in segments)
    total_gain_m = sum(seg["elevation_gain_m"] for seg in segments)
    total_loss_m = sum(seg["elevation_loss_m"] for seg in segments)

    return {
        "segments": segments,
        "totals": {
            "distance_m": round(total_distance_m, 1),
            "elevation_gain_m": round(total_gain_m, 1),
            "elevation_loss_m": round(total_loss_m, 1),
            "time_s": passages["totals_s"],
        },
        "segment_passages": passages["segment_passages"],
        "aid_station_passages": passages["aid_station_passages"],
        "cutoffs": cutoffs,
        "provenance_summary": provenance_summary(segments),
        "band": band,
        "flat_reference_speed_ms": (round(flat_reference_speed_ms, 3) if flat_reference_speed_ms else None),
        "intensity_factor": round(intensity_factor, 4),
        "intensity_source": intensity_source,
        "fade_pct": fade_pct,
        "fade_pct_applied": round(fade_pct_applied, 2),
        "fade_source": fade_source,
        "fade_notes": fade_notes,
        "heat_factor": round(heat_factor, 3),
        "heat_notes": heat_notes,
        "start_time": start_time,
        "race_date": race_date,
        "warnings": warnings,
        "assumptions": ASSUMPTIONS,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_fade(conn, today_date: date, args) -> Tuple[float, str]:
    """Fade médian des sorties longues récentes (#48), ou repli générique
    documenté — voir `ASSUMPTIONS["fade"]`. `conn` déjà ouvert/indexé par
    l'appelant (`main`, revue de code #59 : un seul passage d'indexation par
    appel CLI, jamais un par résolveur)."""
    if args.fade_pct is not None:
        return float(args.fade_pct), "override"
    import arc_index as IDX  # noqa: E402 (import tardif, voir docstring du module)
    trend = IDX.durability_trend(conn, today_date, args.fade_weeks or DEFAULT_FADE_WEEKS)
    measured = [p["gap_fade_pct"] for p in trend.get("points", []) if p.get("gap_fade_pct") is not None]
    if measured:
        return round(statistics.median(measured), 2), "durability_median"
    return DEFAULT_GENERIC_FADE_PCT, "generic"


def _resolve_model_bins(conn, conf: dict, args) -> Tuple[List[dict], Optional[float]]:
    """Paniers du modèle personnel + référence plate de la bande (voir
    `ASSUMPTIONS["base_pace"]`)."""
    import arc_index as IDX  # noqa: E402
    if args.months is not None:
        report = IDX.recompute_slope_model(conn, conf, args.band, args.months, args.today)
    else:
        report = IDX.slope_model_report(conn, args.band)
    return report.get("bins") or [], report.get("flat_reference_speed_ms")


def _resolve_acclimated(conn, conf: dict, today_date: date,
                         temp_max_c: Optional[float]) -> Tuple[Optional[bool], Optional[str]]:
    """`(acclimated, note)` — voir `ASSUMPTIONS["heat"]` : `None` (statut
    inconnu, jamais assimilé à une non-acclimatation) dès que la fenêtre de 14
    jours n'a AUCUNE séance exploitable (`sessions_considered == 0`), pas
    seulement aucune séance chaude."""
    if temp_max_c is None or temp_max_c <= HEAT_HOT_C:
        return None, None
    import arc_index as IDX  # noqa: E402
    report = IDX.heat_acclimation_today(conn, conf, today_date)
    if not report.get("sessions_considered"):
        return None, None
    hot_sessions = report.get("hot_sessions")
    if hot_sessions is None:
        return None, None
    note = f"acclimatation chaleur évaluée sur les 14 jours précédant {today_date.isoformat()} (#38)"
    return hot_sessions >= HEAT_ACCLIMATION_MIN_HOT_SESSIONS, note


def _flat_equivalent_m(distance_m: Optional[float], elevation_gain_m: Optional[float], primary: str) -> float:
    """Distance équivalente plat (`arc_metrics.TRAIL_FLAT_M_PER_M_DPLUS`, trail
    uniquement — voir `ASSUMPTIONS["base_pace"]`). `0.0` si `distance_m` est
    absent."""
    if not distance_m or distance_m <= 0:
        return 0.0
    flat_m = distance_m
    if primary == "trail" and elevation_gain_m:
        flat_m += elevation_gain_m * M.TRAIL_FLAT_M_PER_M_DPLUS
    return flat_m


def _select_hard_reference(conn, conf: dict) -> Optional[dict]:
    """Meilleur effort RÉCENT et DUR (planifié tempo+/seuil/VO2max/course, ou à
    défaut de plan FC moyenne au-dessus de la borne Z3/Z4 de l'athlète) — voir
    `ASSUMPTIONS["base_pace"]` (2ᵉ revue de code #59, BLOQUANT) : un footing
    facile, même long, n'est PAS une référence d'allure de COURSE. Rend
    l'activité (dict) la plus LONGUE parmi les qualifiantes (la plus
    prédictive — même principe que `arc_metrics.predictions`), ou `None`."""
    import arc_index as IDX  # noqa: E402 (import tardif, voir docstring du module)
    bounds = IDX.athlete_hr_zone_bounds(conn, conf)
    hard_hr_threshold = bounds[0][3] if bounds else None
    best = None
    for row in conn.execute(
            "SELECT date, sport, distance_m, duration_s, elevation_gain_m, avg_hr_bpm FROM activity "
            "WHERE sport IN ('running', 'trail') AND distance_m >= ? AND duration_s > 0",
            (MIN_REFERENCE_DISTANCE_M,)).fetchall():
        act = dict(row)
        planned = IDX.planned_intensity_for(conn, act.get("date"), act.get("sport"))
        if planned is not None:
            is_hard = planned in HARD_REFERENCE_INTENSITIES
        else:
            is_hard = (hard_hr_threshold is not None and act.get("avg_hr_bpm") is not None
                       and act["avg_hr_bpm"] >= hard_hr_threshold)
        if not is_hard:
            continue
        if best is None or act["distance_m"] > best["distance_m"]:
            best = act
    return best


def _resolve_intensity_factor(conn, conf: dict, flat_reference_speed_ms: Optional[float],
                               gpx_distance_m: Optional[float],
                               gpx_elevation_gain_m: Optional[float]) -> Tuple[float, str, Optional[float], List[str]]:
    """`(intensity_factor, intensity_source, race_flat_speed_ms, notes)` — voir
    `ASSUMPTIONS["base_pace"]`. `intensity_source` : `"riegel"` (méthode
    retenue en priorité, référence dure exigée), `"vdot"` (repli) ou `"none"`
    (facteur `1.0`, allure d'endurance inchangée). La cible est TOUJOURS le
    GPX analysé (`gpx_distance_m`/`gpx_elevation_gain_m`), jamais `planning/
    active_objective.md` (2ᵉ revue de code #59, BLOQUANT) — un avertissement
    est ajouté à `notes` si l'objectif diffère sensiblement du GPX."""
    notes: List[str] = []
    if not flat_reference_speed_ms or flat_reference_speed_ms <= 0:
        return 1.0, "none", None, notes
    primary = conf.get("sport", "trail")
    target_flat_m = _flat_equivalent_m(gpx_distance_m, gpx_elevation_gain_m, primary)
    if target_flat_m <= 0:
        return 1.0, "none", None, notes

    obj = conn.execute("SELECT distance_m, elevation_gain_m FROM objective LIMIT 1").fetchone()
    if obj and obj["distance_m"]:
        obj_flat_m = _flat_equivalent_m(obj["distance_m"], obj["elevation_gain_m"], primary)
        if obj_flat_m > 0 and abs(obj_flat_m - target_flat_m) / obj_flat_m * 100.0 > OBJECTIVE_GPX_MISMATCH_PCT:
            notes.append(
                f"l'objectif actif ({obj['distance_m']:.0f} m / {obj['elevation_gain_m'] or 0:.0f} m D+) et "
                f"le GPX analysé ({gpx_distance_m:.0f} m / {gpx_elevation_gain_m or 0:.0f} m D+) diffèrent "
                f"de plus de {OBJECTIVE_GPX_MISMATCH_PCT:g} % en équivalent plat : l'intensité de course "
                "est calculée depuis LE GPX, pas depuis l'objectif.")

    exponent = M.RIEGEL_EXPONENT.get(primary, M.RIEGEL_EXPONENT["road"])
    predicted_s: Optional[float] = None
    source = "none"
    reference = _select_hard_reference(conn, conf)
    if reference:
        reference_flat_m = _flat_equivalent_m(reference["distance_m"], reference.get("elevation_gain_m"), primary)
        predicted_s = M.riegel(reference["duration_s"], reference_flat_m, target_flat_m, exponent)
        source = "riegel"
    if not predicted_s:
        vo2max_row = conn.execute(
            "SELECT vo2max FROM metric_day WHERE vo2max IS NOT NULL ORDER BY date DESC LIMIT 1").fetchone()
        current_vdot = vo2max_row["vo2max"] if vo2max_row else None
        if current_vdot:
            predicted_s = M.predict_time_vdot(current_vdot, target_flat_m)
            source = "vdot"
    if not predicted_s or predicted_s <= 0:
        return 1.0, "none", None, notes

    race_flat_speed_ms = target_flat_m / predicted_s
    factor = race_flat_speed_ms / flat_reference_speed_ms

    # Plancher (2ᵉ revue de code #59, BLOQUANT) — voir ASSUMPTIONS["base_pace"] :
    # sous `INTENSITY_CLAMP_DURATION_S` (4h30), un facteur < 1.0 est implausible
    # (l'allure de course ne peut pas être plus lente que l'allure d'endurance
    # mesurée sur une distance courte). Aucun plancher au-delà : l'exposant de
    # Riegel en trail (1.15) prédit déjà, à raison, un ralentissement marqué.
    if predicted_s < INTENSITY_CLAMP_DURATION_S and factor < 1.0:
        notes.append(
            f"facteur d'intensité calculé ({factor:.2f}) sous 1.0 pour une course prédite de "
            f"{predicted_s / 3600.0:.1f} h (< {INTENSITY_CLAMP_DURATION_S / 3600.0:.1f} h) : implausible "
            "(l'allure de course ne peut pas être plus lente que l'allure d'endurance mesurée sur cette "
            "distance) — plafonné à 1.0.")
        factor = 1.0

    return factor, source, race_flat_speed_ms, notes


def _load_aid_stations(path: Optional[str]) -> List[dict]:
    if not path:
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("--aid-stations : une liste JSON d'objets {km, name, cutoff?, cutoff_day?, stop_s?} "
                          "attendue")
    return data


def _read_temp_max_c(args) -> Optional[float]:
    if args.temp_max_c is not None:
        return float(args.temp_max_c)
    if args.weather_file:
        text = Path(args.weather_file).read_text(encoding="utf-8")
        block = C.extract_block(text)
        if block:
            return block.get("temp_max_c")
    return None


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Allures de course par segment depuis le modèle personnel pente -> allure (#59).")
    ap.add_argument("command", choices=("plan",), help="sous-commande (seule « plan » existe pour l'instant)")
    ap.add_argument("--gpx", required=True, type=Path, help="fichier GPX de la course")
    ap.add_argument("--workspace", help="racine du workspace (défaut : répertoire courant)")
    ap.add_argument("--db", help="chemin de l'index SQLite (défaut : <workspace>/.arc/coach.db)")
    ap.add_argument("--memory", action="store_true", help="index en mémoire (tests)")
    ap.add_argument("--rebuild", action="store_true", help="repart de zéro pour l'index")
    ap.add_argument("--today", metavar="AAAA-MM-JJ", help="date de fin des séries pour les tendances (durabilité)")
    ap.add_argument("--band", choices=SL.BANDS, default=DEFAULT_BAND,
                     help="bande d'effort du modèle personnel (défaut « endurance »)")
    ap.add_argument("--months", type=int, help="recalcule le modèle sur N mois au lieu du modèle déjà stocké")
    ap.add_argument("--segment-m", type=float, default=DEFAULT_SEGMENT_M, dest="segment_m",
                     help="longueur cible d'un segment, en mètres (défaut 750)")
    ap.add_argument("--race-date", metavar="AAAA-MM-JJ", dest="race_date", help="date de la course")
    ap.add_argument("--start", default="07:00", help="heure de départ HH:MM (défaut 07:00)")
    ap.add_argument("--aid-stations", dest="aid_stations_path",
                     help="fichier JSON : liste d'objets {km, name, cutoff?, cutoff_day?, stop_s?}")
    ap.add_argument("--official-distance-m", type=float, dest="official_distance_m",
                     help="distance officielle de course (m) : rééchelonne les km de ravitaillement sur "
                          "la distance réellement mesurée du GPX")
    ap.add_argument("--fade-pct", type=float, dest="fade_pct",
                     help="fade (%%) explicite — sans cette option, médiane des sorties longues récentes "
                          "(#48) ou repli générique documenté")
    ap.add_argument("--fade-weeks", type=int, dest="fade_weeks",
                     help=f"fenêtre de la tendance de durabilité, semaines (défaut {DEFAULT_FADE_WEEKS})")
    ap.add_argument("--temp-max-c", type=float, dest="temp_max_c",
                     help="température maximale prévue le jour de la course (°C)")
    ap.add_argument("--weather-file", dest="weather_file",
                     help="fichier météo persisté (kind=weather) : temp_max_c lu depuis son bloc ```arc")
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if not args.gpx.exists():
        print(f"ERREUR : fichier GPX introuvable — {args.gpx}", file=sys.stderr)
        return 1
    pts = parse_gpx(args.gpx)
    if len(pts) < 2:
        print(f"ERREUR : GPX sans trace exploitable — {args.gpx}", file=sys.stderr)
        return 1
    try:
        hh, mm = _parse_hhmm(args.start, label="--start")
    except ValueError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    print(f"heure de départ effective : {hh:02d}:{mm:02d}", file=sys.stderr)

    workspace = Path(args.workspace) if args.workspace else Path(".")

    # Index ouvert et reconstruit UNE SEULE FOIS (revue de code #59 : trois
    # réindexations indépendantes coûtaient ≈ 7,6 s contre ≈ 2,5 s pour une
    # seule) — chaque résolveur reçoit `conn`/`conf` déjà prêts.
    import arc_index as IDX
    conn = IDX.open_db(workspace, args.db, args.memory, args.rebuild)
    IDX.index_workspace(conn, workspace, args.today)
    conf = IDX.settings(IDX.load_config(workspace))
    today_date = date.fromisoformat(args.today) if args.today else date.today()

    bins, flat_reference_speed_ms = _resolve_model_bins(conn, conf, args)
    fade_pct, fade_source = _resolve_fade(conn, today_date, args)
    temp_max_c = _read_temp_max_c(args)
    acclimated, acclimation_note = _resolve_acclimated(conn, conf, today_date, temp_max_c)
    # La cible d'intensité est TOUJOURS le GPX ANALYSÉ, jamais l'objectif (voir
    # ASSUMPTIONS["base_pace"], 2ᵉ revue de code #59, BLOQUANT).
    gpx_distance_m, gpx_elevation_gain_m, _gpx_elevation_loss_m = course_totals(pts)
    intensity_factor, intensity_source, _race_flat_speed, intensity_notes = _resolve_intensity_factor(
        conn, conf, flat_reference_speed_ms, gpx_distance_m, gpx_elevation_gain_m)
    aid_stations = _load_aid_stations(args.aid_stations_path)

    try:
        plan = build_race_plan(
            pts, bins, aid_stations=aid_stations, fade_pct=fade_pct, fade_source=fade_source,
            temp_max_c=temp_max_c, acclimated=acclimated, acclimation_note=acclimation_note,
            intensity_factor=intensity_factor, intensity_source=intensity_source,
            intensity_notes=intensity_notes,
            flat_reference_speed_ms=flat_reference_speed_ms, band=args.band,
            official_distance_m=args.official_distance_m,
            start_time=args.start, race_date=args.race_date, segment_m=args.segment_m)
    except ValueError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    print(json.dumps(plan, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
