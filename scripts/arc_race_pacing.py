#!/usr/bin/env python3
"""Allures de course par segment depuis le modèle personnel pente -> allure
(#59, épopée #23).

## Pourquoi

Les scénarios ×3 du plan de course (`agents/course-strategist.md`) reposaient
sur des règles génériques (« +2-3 % par 10 km », « sable -> ×1.2-1.3 »),
jamais sur l'historique réel de l'athlète. Ce module consomme les briques déjà
posées par les épopées précédentes — `arc_slope_model.predict_speed` (#58,
courbe personnelle pente -> allure), `arc_durability` (#48, fade de fin de
sortie longue) — et les combine à un fichier GPX de course pour produire des
temps de passage PAR SEGMENT, avec leur provenance (personnel vs générique),
trois scénarios documentés et une vérification de barrières horaires.

Sert aussi de socle à #61 (débrief post-course, comparaison plan vs réalisé
PAR SEGMENT) : les identifiants de segment (`s01`, `s02`…) et leurs bornes
kilométriques sont stables d'un appel à l'autre pour un même GPX et un même
`--segment-m` (déterminisme, voir `ASSUMPTIONS["segmentation"]`) — #61 doit
pouvoir aligner un segment du plan avec le même segment mesuré après course
sans recalculer sa propre segmentation.

## Découpage en couches (comme le reste du moteur)

- **Segmentation** (`segment_course`) : pure, ne dépend que du GPX (via
  `arc_elevation.grade_series`, déjà partagé par le GAP/#44 et l'analyse GPX
  générique du skill `gpx-analysis`).
- **Prédiction** (`predict_segments`) : pure, ne dépend que des segments, des
  paniers du modèle personnel (`arc_slope_model.predict_speed`), d'un taux de
  fade et d'un facteur météo déjà résolus par l'appelant — aucun accès disque
  ni réseau ici.
- **Passages/barrières** (`compute_passages`) : pure, cumul des temps de
  segment + arrêts ravito, comparaison aux barrières horaires.
- **CLI** (`plan`, fonction `main`) : la SEULE couche qui touche le disque —
  lit le GPX, ouvre l'index du workspace (`arc_index`, mêmes conventions que
  les autres sous-commandes : `--workspace`, `--db`, `--memory`, `--rebuild`,
  `--today`) pour résoudre le modèle personnel et la tendance de durabilité,
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
jamais une seconde implémentation de ces calculs.

## Segmentation (voir `ASSUMPTIONS["segmentation"]`)

Longueur cible fixe (`--segment-m`, défaut 750 m — au milieu de la fourchette
500 m-1 km demandée par #59), puis une passe de fusion GREEDY de gauche à
droite : deux segments adjacents dont la pente moyenne diffère de moins de
`MERGE_GRADE_DELTA_PCT` (2 points) sont fusionnés, tant que le segment fusionné
ne dépasse pas `MAX_SEGMENT_M` (2× la cible) — évite une avalanche de tout
petits segments sur un profil plat tout en gardant un côté déterministe et un
plafond de longueur pour ne jamais dissoudre une vraie rupture de pente dans
un segment démesuré. Le dernier segment, s'il est plus court que
`MIN_SEGMENT_M`, est fusionné dans le précédent plutôt que laissé orphelin.

## Fade (voir `ASSUMPTIONS["fade"]`)

Le fade GAP médian des sorties longues récentes (`arc_durability`, #48) est
appliqué comme un ralentissement PROGRESSIF : nul sur le premier tiers de la
course (même repère que la mesure elle-même, qui compare premier et dernier
tiers), puis une rampe LINÉAIRE du premier tiers jusqu'à la fin, où le
ralentissement complet (`fade_pct`) est atteint — jamais un ralentissement
brutal ni un fade appliqué dès le kilomètre 0, ce que la mesure source ne
justifie pas.

## Chaleur (voir `ASSUMPTIONS["heat"]`)

Reprend TELS QUELS les seuils déjà documentés dans `agents/course-strategist.md`
(ÉTAPE 6, approximation du projet, jamais une source physiologique
vérifiable pour ces pourcentages précis) : > 25 °C -> +10 % de temps,
< 5 °C -> +5 % de temps — avec un supplément de +5 % si la course est prévue
chaude ET que l'athlète a peu été exposé à la chaleur récemment
(`arc_index.heat_acclimation_today`, #38) : un pari optimiste sur une
acclimatation supposée serait plus dangereux qu'un plan trop prudent.

## Scénarios (voir `ASSUMPTIONS["scenarios"]`)

Quand un segment est prédit par le modèle PERSONNEL, les trois scénarios
utilisent directement la dispersion déjà calculée par panier
(`arc_slope_model` : IQR pondéré p25/p50/p75, exposé par `predict_speed` comme
`ci_low_speed_ms`/`speed_ms`/`ci_high_speed_ms`) — jamais un pourcentage
inventé quand une vraie dispersion mesurée existe. Un segment générique ou
mixte (pas de dispersion, `ci_*` à `None`) retombe sur un pourcentage fixe
documenté (`GENERIC_SCENARIO_SPEED_FACTOR`), signalé comme approximation du
projet.

Jamais de fausse précision : les temps de segment sont arrondis à la seconde
la plus proche (secondes < 1 km n'ont aucun sens physique) mais les temps de
passage CUMULÉS sont arrondis à la minute — un plan de course n'a jamais la
précision de la seconde sur plusieurs heures d'effort.

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
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arc_contract as C  # noqa: E402
import arc_elevation as EL  # noqa: E402
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
# ils encadrent la cible d'un ordre de grandeur raisonnable (±6-8 %), jamais
# une vraie mesure de dispersion individuelle.
GENERIC_SCENARIO_SPEED_FACTOR = {"safe": 0.92, "realistic": 1.0, "ambitious": 1.06}

# Fade générique de repli (#59, ASSUMPTIONS["fade"]) : appliqué UNIQUEMENT si
# aucune sortie longue récente n'a de fade GAP mesurable (`arc_durability`) —
# approximation du projet, pas une mesure. Volontairement modeste : un plan de
# course ne doit pas supposer un effondrement qu'aucune donnée ne suggère.
DEFAULT_GENERIC_FADE_PCT = 5.0

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

ASSUMPTIONS = {
    "segmentation": (
        "Segments de longueur cible fixe (`DEFAULT_SEGMENT_M`, 750 m — milieu de la fourchette "
        "500 m-1 km demandée par #59), pente moyenne calculée par distance parcourue (pondérée) sur "
        "le profil d'altitude lissé (`arc_elevation.grade_series`, fenêtre 30 m, même moteur que le "
        "GAP #44 et l'analyse GPX générique du skill gpx-analysis). Une passe de fusion GREEDY, de "
        "gauche à droite, fusionne deux segments adjacents dont la pente moyenne diffère de moins de "
        "`MERGE_GRADE_DELTA_PCT` (2 points), tant que le segment fusionné ne dépasse pas "
        "`MAX_SEGMENT_FACTOR` × la longueur cible (2250 m par défaut) — réduit la fragmentation sur un "
        "profil plat sans jamais dissoudre une vraie rupture de pente dans un segment démesuré. Le "
        "dernier segment, s'il est plus court que `MIN_SEGMENT_M` (300 m), est fusionné dans le "
        "précédent plutôt que laissé orphelin. Déterministe pour un GPX et un `--segment-m` donnés : "
        "mêmes identifiants (`s01`, `s02`…) et mêmes bornes kilométriques d'un appel à l'autre — "
        "propriété nécessaire à #61 (débrief post-course par segment)."
    ),
    "scenarios": (
        "Un segment prédit par le modèle PERSONNEL (`source == \"personal\"`) utilise directement la "
        "dispersion déjà calculée par panier de pente (`arc_slope_model`, IQR pondéré p25/p50/p75, "
        "exposée par `predict_speed` comme `ci_low_speed_ms`/`speed_ms`/`ci_high_speed_ms`) : "
        "« safe » = p25 (plus lent), « realistic » = médiane/interpolation, « ambitious » = p75 (plus "
        "rapide) — jamais un pourcentage inventé quand une vraie dispersion mesurée existe. Un "
        "segment générique ou mixte (`ci_*` à `None`, voir `arc_slope_model.predict_speed`) retombe "
        "sur un pourcentage fixe documenté (`GENERIC_SCENARIO_SPEED_FACTOR`, ±6-8 %), signalé comme "
        "approximation du projet, sans source vérifiable pour ces valeurs précises."
    ),
    "fade": (
        "Le fade GAP médian des sorties longues récentes (`arc_durability`/`arc_index.durability_trend`, "
        "#48, fenêtre `--fade-weeks`, défaut 12 semaines glissantes) est appliqué comme un "
        "ralentissement PROGRESSIF sur la vitesse : nul sur le premier tiers de la distance totale de "
        "la course (même repère que la mesure source, qui compare premier et dernier tiers d'une sortie "
        "longue), puis une rampe LINÉAIRE du premier tiers jusqu'à l'arrivée, où le ralentissement "
        "complet (`fade_pct`) est atteint. Sans aucune sortie longue avec un fade GAP mesurable dans la "
        "fenêtre, un fade générique de repli est utilisé (`DEFAULT_GENERIC_FADE_PCT`, 5 %) — "
        "approximation du projet, PAS une mesure, toujours signalée (`fade_source: \"generic\"` dans la "
        "sortie) pour que le plan ne prétende jamais à une précision qu'il n'a pas."
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
        "tous les segments (pas de section plus/moins exposée modélisée ici)."
    ),
    "aid_stations": (
        "Chaque ravitaillement ajoute un temps d'arrêt FIXE au cumul (`stop_s` de la station si fourni, "
        "sinon `DEFAULT_AID_STATION_STOP_S`, 90 s — approximation du projet, un ravito simple) — "
        "identique pour les trois scénarios (aucune donnée ne justifie un arrêt plus long pour un "
        "scénario plus lent)."
    ),
    "cutoffs": (
        "Une barrière horaire (`aid_station.cutoff`, HH:MM le jour de la course) est comparée à l'heure "
        "de passage CUMULÉE de chaque scénario (départ + temps de segment + arrêts ravito). Marge = "
        "barrière − passage. `\"ok\"` si marge ≥ `CUTOFF_MARGIN_OK_S` (30 min — approximation du "
        "projet, pas une règle de course réelle), `\"tendu\"` si 0 ≤ marge < 30 min, `\"hors_delai\"` "
        "si marge < 0 (le scénario n'atteindrait pas la barrière)."
    ),
    "provenance": (
        "`provenance_summary` rend la part de distance totale prédite par segment `personal`/"
        "`generic`/`mixed` (`arc_slope_model.predict_speed.source`) — le critère d'acceptation #59 "
        "(« le plan indique la provenance par segment ») est vérifiable directement sur `segments[].source`, "
        "ce résumé n'est qu'un agrégat pratique pour l'affichage."
    ),
}


# ---------------------------------------------------------------------------
# GPX -> points (duplication volontaire et minimale de
# `skills/gpx-analysis/scripts/analyze_gpx.parse_gpx`/`haversine` : le moteur
# racine ne doit jamais dépendre d'un script de skill, voir le docstring du
# module — sens de dépendance unique skill -> moteur, jamais l'inverse).
# ---------------------------------------------------------------------------

def parse_gpx(path: Path) -> List[dict]:
    """Extrait la liste ordonnée des points {lat, lon, ele} du premier trk/trkseg."""
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


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

def _weighted_mean(values: Sequence[Optional[float]], weights: Sequence[float]) -> Optional[float]:
    pairs = [(v, w) for v, w in zip(values, weights) if v is not None and w > 0]
    if not pairs:
        return None
    total_w = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / total_w


def _raw_segment(pts: Sequence[dict], dist: Sequence[float], grades: Sequence[Optional[float]],
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
    }


def _merge_raw(a: dict, pts: Sequence[dict], dist: Sequence[float], grades: Sequence[Optional[float]],
               ele_smooth: Sequence[Optional[float]], b: dict) -> dict:
    return _raw_segment(pts, dist, grades, ele_smooth, a["i_start"], b["i_end"])


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

    Chaque segment : `id` (`s01`, `s02`…), `km_start`, `km_end`, `distance_m`,
    `grade_mean_pct` (signé, `None` si non calculable sur tout le segment),
    `elevation_gain_m`, `elevation_loss_m`."""
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
            raws.append(_raw_segment(pts, dist, grades, ele_smooth, i_start, i))
            i_start = i
            next_boundary = dist[i] + target_segment_m
            if i == n - 1:
                break
    if not raws:
        raws = [_raw_segment(pts, dist, grades, ele_smooth, 0, n - 1)]

    # 2) Fusion du dernier segment s'il est trop court.
    if len(raws) > 1 and raws[-1]["distance_m"] < min_segment_m:
        raws[-2] = _merge_raw(raws[-2], pts, dist, grades, ele_smooth, raws[-1])
        raws.pop()

    # 3) Fusion greedy des segments adjacents de pente similaire, plafonnée en
    # longueur (voir ASSUMPTIONS["segmentation"]).
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
                merged[-1] = _merge_raw(prev, pts, dist, grades, ele_smooth, seg)
                continue
        merged.append(dict(seg))

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
        })
    return out


# ---------------------------------------------------------------------------
# Prédiction par segment
# ---------------------------------------------------------------------------

def fade_speed_multiplier(km_frac: float, fade_pct: float) -> float:
    """Multiplicateur de vitesse (<= 1.0) au point `km_frac` (0-1, fraction de
    la distance totale de course) pour un fade GAP `fade_pct` (%) mesuré entre
    premier et dernier tiers d'une sortie longue — voir `ASSUMPTIONS["fade"]`.
    Nul avant le premier tiers, rampe linéaire ensuite jusqu'à `fade_pct`
    complet à l'arrivée (`km_frac == 1.0`)."""
    if fade_pct <= 0 or km_frac <= 1.0 / 3.0:
        return 1.0
    t = min(1.0, (km_frac - 1.0 / 3.0) / (2.0 / 3.0))
    return 1.0 - t * (fade_pct / 100.0)


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
                         f"{HEAT_UNACCLIMATED_EXTRA_FACTOR:g} (approximation du projet)")
    elif temp_max_c < HEAT_COLD_C:
        factor *= HEAT_COLD_TIME_FACTOR
        notes.append(f"froid prévu ({temp_max_c:g} °C < {HEAT_COLD_C:g} °C) : temps × {HEAT_COLD_TIME_FACTOR:g} "
                     "(approximation du projet)")
    return factor, notes


def _scenario_speeds(prediction: dict) -> Dict[str, Optional[float]]:
    speed = prediction.get("speed_ms")
    if speed is None:
        return {s: None for s in SCENARIOS}
    ci_low, ci_high = prediction.get("ci_low_speed_ms"), prediction.get("ci_high_speed_ms")
    if ci_low is not None and ci_high is not None:
        return {"safe": ci_low, "realistic": speed, "ambitious": ci_high}
    return {s: speed * GENERIC_SCENARIO_SPEED_FACTOR[s] for s in SCENARIOS}


def predict_segments(segments: Sequence[dict], bins: Sequence[dict], *,
                      fade_pct: float = 0.0, heat_factor: float = 1.0) -> List[dict]:
    """Augmente chaque segment (`segment_course`) d'une prédiction de temps par
    scénario — pure, aucun accès disque. `bins` : `model["bins"]` d'un rapport
    `arc_slope_model.fit_slope_model`/`arc_index.slope_model_report`.

    Rend une COPIE des segments, chacun augmenté de `source`, `reason_code`
    (informationnel, ex. `"extrapolated"`), `predicted_time_s` (objet par
    scénario, secondes arrondies), `pace_s_km` (objet par scénario), `notes`
    (liste de courtes explications, ex. extrapolation)."""
    total_m = sum(seg["distance_m"] for seg in segments) or 1.0
    cum_m = 0.0
    out = []
    for seg in segments:
        seg_start_frac = cum_m / total_m
        seg_mid_frac = (cum_m + seg["distance_m"] / 2.0) / total_m
        cum_m += seg["distance_m"]

        grade = seg["grade_mean_pct"] / 100.0 if seg["grade_mean_pct"] is not None else None
        prediction = SL.predict_speed(grade, bins)
        scenario_speeds = _scenario_speeds(prediction)
        fade_mult = fade_speed_multiplier(seg_mid_frac, fade_pct)

        predicted_time_s: Dict[str, Optional[float]] = {}
        pace_s_km: Dict[str, Optional[float]] = {}
        for scenario, base_speed in scenario_speeds.items():
            if base_speed is None or base_speed <= 0:
                predicted_time_s[scenario] = None
                pace_s_km[scenario] = None
                continue
            effective_speed = base_speed * fade_mult / heat_factor
            t = seg["distance_m"] / effective_speed if effective_speed > 0 else None
            predicted_time_s[scenario] = round(t, 1) if t is not None else None
            pace_s_km[scenario] = round(1000.0 / effective_speed, 1) if effective_speed > 0 else None

        notes = []
        if prediction.get("reason_code") == "extrapolated":
            notes.append("pente hors plage du modèle personnel : vitesse prolongée à plat (extrapolation)")
        if prediction.get("reason_code") == "no_model":
            notes.append("aucun modèle personnel disponible : ce segment ne peut pas être prédit")

        out.append({
            **{k: v for k, v in seg.items()},
            "source": prediction.get("source"),
            "reason_code": prediction.get("reason_code"),
            "predicted_time_s": predicted_time_s,
            "pace_s_km": pace_s_km,
            "notes": notes,
            "km_frac_start": round(seg_start_frac, 4),
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

def compute_passages(segments: Sequence[dict], aid_stations: Sequence[dict]) -> dict:
    """Temps de passage cumulés par scénario à la fin de CHAQUE segment, plus
    les arrêts ravito (voir `ASSUMPTIONS["aid_stations"]`). Rend
    `{"segment_passages": [...], "totals_s": {...}, "aid_station_passages": [...]}`.

    `segment_passages[i]` : `{"segment_id", "km_end", scenario: cumulative_s}`
    (cumul APRÈS le segment, arrêts ravito déjà traversés compris).
    `aid_station_passages` : une entrée par station fournie, avec le temps
    cumulé d'ARRIVÉE à la station (avant son propre arrêt) par scénario."""
    cum = {s: 0.0 for s in SCENARIOS}
    segment_passages = []
    aid_idx = 0
    aid_sorted = sorted(aid_stations, key=lambda a: a["km"])
    aid_station_passages = []
    for seg in segments:
        for scenario in SCENARIOS:
            t = seg["predicted_time_s"].get(scenario)
            if t is not None:
                cum[scenario] += t
        segment_passages.append({"segment_id": seg["id"], "km_end": seg["km_end"], **{s: round(cum[s]) for s in SCENARIOS}})
        while aid_idx < len(aid_sorted) and aid_sorted[aid_idx]["km"] <= seg["km_end"]:
            station = aid_sorted[aid_idx]
            aid_station_passages.append({
                "km": station["km"], "name": station.get("name"),
                **{s: round(cum[s]) for s in SCENARIOS},
            })
            stop_s = station.get("stop_s", DEFAULT_AID_STATION_STOP_S)
            for scenario in SCENARIOS:
                cum[scenario] += stop_s
            aid_idx += 1
    totals_s = {s: round(cum[s]) for s in SCENARIOS}
    return {"segment_passages": segment_passages, "totals_s": totals_s, "aid_station_passages": aid_station_passages}


def check_cutoffs(aid_station_passages: Sequence[dict], aid_stations: Sequence[dict],
                   start_dt: datetime) -> List[dict]:
    """Marge de chaque scénario face à une barrière horaire (`aid_station.cutoff`,
    HH:MM le jour de la course) — voir `ASSUMPTIONS["cutoffs"]`. Une station
    sans `cutoff` n'apparaît pas dans le résultat (rien à vérifier)."""
    by_km = {round(a["km"], 6): a for a in aid_stations if a.get("cutoff")}
    out = []
    for passage in aid_station_passages:
        station = by_km.get(round(passage["km"], 6))
        if station is None:
            continue
        try:
            hh, mm = (int(x) for x in station["cutoff"].split(":"))
        except (ValueError, AttributeError):
            continue
        cutoff_dt = start_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if cutoff_dt < start_dt:
            cutoff_dt += timedelta(days=1)
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

def build_race_plan(pts: Sequence[dict], bins: Sequence[dict], *,
                     aid_stations: Optional[Sequence[dict]] = None,
                     fade_pct: float = 0.0, fade_source: str = "generic",
                     temp_max_c: Optional[float] = None, acclimated: Optional[bool] = None,
                     start_time: str = "07:00", race_date: Optional[str] = None,
                     segment_m: float = DEFAULT_SEGMENT_M) -> dict:
    """Assemble le plan de course complet — pure (aucun accès disque), pour que
    la CLI et les tests partagent exactement le même chemin de calcul."""
    aid_stations = list(aid_stations or [])
    raw_segments = segment_course(pts, target_segment_m=segment_m)
    heat_factor, heat_notes = heat_time_factor(temp_max_c, acclimated=acclimated)
    segments = predict_segments(raw_segments, bins, fade_pct=fade_pct, heat_factor=heat_factor)

    try:
        hh, mm = (int(x) for x in start_time.split(":"))
    except ValueError:
        hh, mm = 7, 0
    base_date = date.fromisoformat(race_date) if race_date else date.today()
    start_dt = datetime(base_date.year, base_date.month, base_date.day, hh, mm)

    passages = compute_passages(segments, aid_stations)
    cutoffs = check_cutoffs(passages["aid_station_passages"], aid_stations, start_dt)

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
        "fade_pct": fade_pct,
        "fade_source": fade_source,
        "heat_factor": round(heat_factor, 3),
        "heat_notes": heat_notes,
        "start_time": start_time,
        "race_date": race_date,
        "assumptions": ASSUMPTIONS,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_fade(workspace: Path, _unused, args) -> Tuple[float, str]:
    """Fade médian des sorties longues récentes (#48), ou repli générique
    documenté — voir `ASSUMPTIONS["fade"]`. Importe `arc_index` à la demande
    (coûteux : ouvre/reconstruit l'index) pour que les fonctions pures
    ci-dessus restent testables sans SQLite."""
    if args.fade_pct is not None:
        return float(args.fade_pct), "override"
    import arc_index as IDX  # noqa: E402 (import tardif, voir docstring)
    conn = IDX.open_db(workspace, args.db, args.memory, args.rebuild)
    IDX.index_workspace(conn, workspace, args.today)
    today_date = date.fromisoformat(args.today) if args.today else date.today()
    trend = IDX.durability_trend(conn, today_date, args.fade_weeks or DEFAULT_FADE_WEEKS)
    measured = [p["gap_fade_pct"] for p in trend.get("points", []) if p.get("gap_fade_pct") is not None]
    if measured:
        return round(statistics.median(measured), 2), "durability_median"
    return DEFAULT_GENERIC_FADE_PCT, "generic"


def _resolve_model_bins(workspace: Path, args) -> List[dict]:
    import arc_index as IDX  # noqa: E402
    conn = IDX.open_db(workspace, args.db, args.memory, args.rebuild)
    IDX.index_workspace(conn, workspace, args.today)
    conf = IDX.settings(IDX.load_config(workspace))
    if args.months is not None:
        report = IDX.recompute_slope_model(conn, conf, args.band, args.months, args.today)
    else:
        report = IDX.slope_model_report(conn, args.band)
    return report.get("bins") or []


def _resolve_acclimated(workspace: Path, args, temp_max_c: Optional[float]) -> Optional[bool]:
    if temp_max_c is None or temp_max_c <= HEAT_HOT_C:
        return None
    import arc_index as IDX  # noqa: E402
    conn = IDX.open_db(workspace, args.db, args.memory, args.rebuild)
    IDX.index_workspace(conn, workspace, args.today)
    conf = IDX.settings(IDX.load_config(workspace))
    today_date = date.fromisoformat(args.today) if args.today else date.today()
    report = IDX.heat_acclimation_today(conn, conf, today_date)
    hot_sessions = report.get("hot_sessions")
    if hot_sessions is None:
        return None
    return hot_sessions >= HEAT_ACCLIMATION_MIN_HOT_SESSIONS


def _load_aid_stations(path: Optional[str]) -> List[dict]:
    if not path:
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("--aid-stations : une liste JSON d'objets {km, name, cutoff?, stop_s?} attendue")
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
                     help="fichier JSON : liste d'objets {km, name, cutoff?, stop_s?}")
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

    workspace = Path(args.workspace) if args.workspace else Path(".")
    bins = _resolve_model_bins(workspace, args)
    fade_pct, fade_source = _resolve_fade(workspace, None, args)
    temp_max_c = _read_temp_max_c(args)
    acclimated = _resolve_acclimated(workspace, args, temp_max_c)
    aid_stations = _load_aid_stations(args.aid_stations_path)

    plan = build_race_plan(
        pts, bins, aid_stations=aid_stations, fade_pct=fade_pct, fade_source=fade_source,
        temp_max_c=temp_max_c, acclimated=acclimated, start_time=args.start, race_date=args.race_date,
        segment_m=args.segment_m)
    print(json.dumps(plan, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
