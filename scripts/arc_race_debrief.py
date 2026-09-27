#!/usr/bin/env python3
"""Débrief post-course : plan vs réalisé, par segment (#61, épopée #23).

## Pourquoi

Aucun concurrent ne débriefe une course contre son PROPRE plan. Ce module
compare un `race_plan` (#59, `scripts/arc_race_pacing.py`, champ `segments`,
identifiants `s01`, `s02`… stables) à l'activité RÉELLEMENT enregistrée pour
cette course, segment par segment : écart d'allure, dérive cumulée, fade de
fin de course (mesuré vs prévu), glucides/h réalisés vs visés, météo réelle
vs prévue si les deux sont connues, et temps de ravitaillement quand des
échantillons FIT (#42) permettent de détecter un arrêt — jamais une valeur
inventée.

`#59` a délibérément rendu la segmentation du plan DÉTERMINISTE pour un même
GPX et un même découpage, précisément pour que ce module puisse aligner un
segment mesuré après course avec le même segment du plan sans recalculer sa
propre segmentation — voir `scripts/arc_race_pacing.py::ASSUMPTIONS["segmentation"]`.

## Alignement plan / réalisé (voir `ASSUMPTIONS["alignment"]`)

Le plan et l'activité mesurent la même course avec deux appareils différents
(le GPX analysé pour construire le plan, la montre le jour J) : leur distance
totale mesurée diffère presque toujours un peu (bruit GPS, filtrage différent).
Comparer des DISTANCES CUMULÉES brutes déciderait donc, à tort, qu'un segment
« finit » avant ou après son vrai emplacement sur le parcours réel. La règle
retenue : les distances cumulées des splits de l'activité sont mises à
l'échelle PROPORTIONNELLEMENT (`plan_distance_m / activity_distance_m`) pour
que le total de l'activité coïncide EXACTEMENT avec le total du plan — jamais
le temps, qui reste la mesure de vérité. Le temps cumulé réel à la borne de
chaque segment du plan est ensuite obtenu par interpolation linéaire entre les
deux points de split (de l'activité, mis à l'échelle) qui l'encadrent — une
approximation qui suppose une allure constante à l'intérieur d'un même
kilomètre de split, la plus fine granularité disponible dans le contrat
(`activity.splits`).

## Ce qui n'est JAMAIS inventé

- **Temps aux ravitos** : seulement si un fichier d'échantillons FIT (#42,
  `--fit`) est fourni ET qu'un arrêt (vitesse quasi nulle, durée soutenue) y
  est détecté à proximité d'un ravito du plan. Sans `--fit`, la clé
  `aid_station_times` est absente du résultat — jamais une durée par défaut.
- **Glucides/h prévus** : aucun champ structuré du contrat ne porte
  aujourd'hui un objectif glucides/h de plan de course (le plan nutrition du
  stratège de course reste un fichier texte libre, voir `agents/course-strategist.md`
  ÉTAPE 5) — l'appelant (l'agent coach) passe l'objectif via `--carbs-target-g-h`
  s'il en connaît un ; sans lui, la comparaison glucides est omise (jamais une
  cible inventée).
- **Météo réelle vs prévue** : seulement si les DEUX fichiers `weather` (#
  prévu au moment du plan, réel du jour J) sont fournis explicitement
  (`--planned-weather`/`--actual-weather`) — le contrat ne conserve pas la
  météo utilisée par `arc_race_pacing.py` dans le bloc `race_plan` persisté.

## Conclusions (`findings`, voir `ASSUMPTIONS["findings"]`)

Règles simples, à seuils documentés, PROPOSÉES à l'athlète — jamais écrites
seules dans `planning/Runner_Profile.md` (fichier édité par l'athlète, voir
`skills/workspace-data-contract/SKILL.md`) : `suggested_profile_updates` reste
une liste de PROPOSITIONS que l'agent doit présenter, jamais appliquer
silencieusement.

Stdlib uniquement (CONTRIBUTING.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arc_contract as C  # noqa: E402
import arc_metrics as M  # noqa: E402

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_SCENARIO = "realistic"

# Au-delà de cet écart (%) entre distance mesurée de l'activité et distance du
# plan, un avertissement est émis (la mise à l'échelle proportionnelle reste
# appliquée dans tous les cas, voir ASSUMPTIONS["alignment"]) — approximation
# du projet, jamais une règle GPS vérifiable.
DISTANCE_MISMATCH_WARN_PCT = 3.0

# Fade (voir ASSUMPTIONS["fade"]) : même repère 1ère moitié / 2ᵉ moitié en
# DISTANCE que la définition usuelle du fade de course (contrairement au fade
# d'ENTRAÎNEMENT de `arc_durability`/`arc_race_pacing`, qui compare 1er et
# dernier TIERS d'une sortie longue) — un débrief de course compare la course
# entière, pas seulement sa fin.
FADE_HALF_FRACTION = 0.5

# Départ trop rapide (`ASSUMPTIONS["findings"]`) : approximation du projet,
# aucune source vérifiable ne fixe ces seuils précis pour CE calcul — ils
# encadrent un ordre de grandeur raisonnable (départ nettement plus vite que
# prévu, suivi d'un fade nettement supérieur à celui déjà anticipé par le plan).
FAST_START_DELTA_PCT_THRESHOLD = -5.0
FAST_START_FADE_EXCESS_PCT_THRESHOLD = 3.0
FAST_START_FRACTION = 1.0 / 3.0  # même repère « premier tiers » que arc_race_pacing (fade)

# Glucides (approximation du projet) : sous l'objectif de plus de cette marge
# relative, signalé comme sous-alimentation ; au-dessus du plafond connu
# (`--carbs-ceiling-g-h`, repris de `scripts/arc_index.py fueling`), signalé
# comme dépassement — jamais une preuve de trouble digestif, voir
# `arc_metrics.ASSUMPTIONS["fueling"]` (« toléré » = « ingéré sans incident
# signalé », jamais une mesure de tolérance).
CARBS_UNDER_TARGET_TOLERANCE_PCT = 15.0

# Détection d'arrêt sur échantillons FIT (#42) — approximation du projet,
# jamais une mesure GPS certifiée : vitesse quasi nulle soutenue plusieurs
# secondes, pas un simple ralentissement dans une côte.
STOP_SPEED_MS_THRESHOLD = 0.3
STOP_MIN_DURATION_S = 20.0
AID_STATION_MATCH_RADIUS_M = 400.0

ASSUMPTIONS = {
    "alignment": (
        "Le plan (GPX analysé en amont) et l'activité réelle (montre le jour J) mesurent presque "
        "toujours des distances totales légèrement différentes pour le même parcours (bruit GPS, "
        "filtrage différent). Comparer des distances cumulées brutes déciderait à tort qu'un segment "
        "finit avant/après son vrai emplacement réel. Règle retenue : les distances cumulées des "
        "splits de l'activité sont mises à l'échelle PROPORTIONNELLEMENT — jamais le temps — par "
        "`plan_distance_m / activity_distance_m`, pour que le total de l'activité coïncide EXACTEMENT "
        "avec celui du plan. Le temps cumulé réel à chaque borne de segment est ensuite interpolé "
        "LINÉAIREMENT entre les deux points de split encadrants (mis à l'échelle) — hypothèse d'allure "
        "constante à l'intérieur d'un même kilomètre de split, la plus fine granularité disponible dans "
        "le contrat (`activity.splits`). Un écart de distance au-delà de "
        "`DISTANCE_MISMATCH_WARN_PCT` (3 %) déclenche un avertissement (qualité GPS à vérifier), mais "
        "la mise à l'échelle est appliquée dans tous les cas, même pour un écart minime."
    ),
    "fade": (
        "Compare la 1ère moitié à la 2ᵉ moitié de la DISTANCE TOTALE (pas le dernier tiers d'une sortie "
        "d'entraînement comme `arc_durability`/`arc_race_pacing` : un débrief de course compare la "
        "course entière). `fade_actual_pct`/`fade_planned_pct` : écart relatif de l'allure moyenne de la "
        "2ᵉ moitié par rapport à la 1ère (positif = ralentissement). `fade_vs_plan_pct` = fade réel moins "
        "fade déjà anticipé par le plan (`arc_race_pacing`, champ `fade_pct_applied` non repris ici — "
        "recalculé directement depuis les `predicted_time_s` par segment, cohérent avec la mise à "
        "l'échelle de temps déjà appliquée au plan). Absent si un segment du plan n'a pas de "
        "`predicted_time_s` pour le scénario choisi (rien à comparer)."
    ),
    "findings": (
        "Règles simples à seuils documentés (approximation du projet, aucune littérature vérifiable ne "
        "fixe ces valeurs précises) : `depart_trop_rapide` si le delta moyen (pondéré par la distance) "
        "du premier tiers de course est sous `FAST_START_DELTA_PCT_THRESHOLD` (-5 %, départ nettement "
        "plus vite que prévu) ET que `fade_vs_plan_pct` dépasse `FAST_START_FADE_EXCESS_PCT_THRESHOLD` "
        "(+3 points, fade nettement supérieur à celui déjà anticipé) — les deux conditions ensemble, "
        "jamais l'une seule (un départ rapide sans fade excédentaire n'est pas un problème). Glucides : "
        "`glucides_sous_objectif` si le débit réalisé est sous l'objectif de plus de "
        "`CARBS_UNDER_TARGET_TOLERANCE_PCT` (15 %) ; `glucides_au_dessus_plafond` si le débit réalisé "
        "dépasse le plafond connu (`--carbs-ceiling-g-h`, repris de `scripts/arc_index.py fueling`) — "
        "jamais présenté comme un trouble digestif prouvé, seulement `sans incident signalé ailleurs` "
        "(même prudence que `arc_metrics.ASSUMPTIONS['fueling']`). Toujours un `ecart_temps_total` "
        "informatif, même sans écart notable. `suggested_profile_updates` reste une liste de "
        "PROPOSITIONS : l'agent doit les présenter à l'athlète, jamais les écrire seul dans "
        "`planning/Runner_Profile.md` (fichier édité par l'athlète)."
    ),
    "aid_stations": (
        "Un temps de ravitaillement n'est rapporté QUE si `--fit` fournit des échantillons (#42, "
        "`t_s`/`distance_m`/`speed_ms`) et qu'un arrêt y est détecté (vitesse sous "
        "`STOP_SPEED_MS_THRESHOLD` pendant au moins `STOP_MIN_DURATION_S`) à moins de "
        "`AID_STATION_MATCH_RADIUS_M` (400 m, mis à l'échelle comme les splits) du ravito du plan. Sans "
        "`--fit`, la clé `aid_station_times` est absente du résultat — jamais une durée par défaut ni "
        "une estimée depuis les splits km (trop grossiers pour distinguer un arrêt d'un simple "
        "ralentissement)."
    ),
}


class DebriefError(ValueError):
    """Donnée d'entrée manquante ou incohérente pour construire un débrief."""


# ---------------------------------------------------------------------------
# Lecture des fichiers ```arc
# ---------------------------------------------------------------------------

def load_block(path: Path, *, expected_kind: str) -> dict:
    if not path.exists():
        raise DebriefError(f"fichier introuvable : {path}")
    text = path.read_text(encoding="utf-8")
    data = C.extract_block(text)
    if data is None:
        raise DebriefError(f"{path} : aucun bloc ```arc trouvé")
    kind = data.get("kind")
    if kind != expected_kind:
        raise DebriefError(f"{path} : kind={kind!r} trouvé, {expected_kind!r} attendu")
    return data


# ---------------------------------------------------------------------------
# Alignement distance/temps
# ---------------------------------------------------------------------------

def build_actual_checkpoints(activity: dict) -> List[Tuple[float, float]]:
    """Points `(distance_m_cumulée, temps_s_cumulé)` de l'activité, un par split
    (voir `activity.splits`/`splits_cols`), triés par km croissant, avec `(0, 0)`
    en tête. `distance_m` du split s'il est renseigné (dernier split partiel),
    sinon 1000 m (un split plein). Lève `DebriefError` si l'activité n'a aucun
    split exploitable (rien à aligner par segment) ou si un split n'a pas de
    `duration_s`."""
    rows = C.split_rows(activity)
    if not rows:
        raise DebriefError("activité sans splits (`splits`/`splits_cols`) : impossible d'aligner par segment")
    rows = sorted(rows, key=lambda r: r.get("km", 0))
    checkpoints: List[Tuple[float, float]] = [(0.0, 0.0)]
    cum_d = cum_t = 0.0
    for row in rows:
        duration = row.get("duration_s")
        if duration is None:
            raise DebriefError(f"split km={row.get('km')} sans duration_s")
        distance = row.get("distance_m")
        cum_d += float(distance) if distance is not None else 1000.0
        cum_t += float(duration)
        checkpoints.append((cum_d, cum_t))
    return checkpoints


def _interpolate_cum_time(checkpoints: Sequence[Tuple[float, float]], target_m: float) -> float:
    """Temps cumulé (s) à `target_m` par interpolation linéaire entre les deux
    points de `checkpoints` (croissants, `(0, 0)` en tête) qui l'encadrent —
    voir `ASSUMPTIONS["alignment"]`. Clampé aux bornes si `target_m` déborde
    (ne devrait pas arriver après mise à l'échelle sur la distance totale du
    plan, sauf incohérence des données d'entrée)."""
    if target_m <= checkpoints[0][0]:
        return checkpoints[0][1]
    for i in range(1, len(checkpoints)):
        d0, t0 = checkpoints[i - 1]
        d1, t1 = checkpoints[i]
        if target_m <= d1 + 1e-9:
            if d1 - d0 <= 0:
                return t1
            frac = (target_m - d0) / (d1 - d0)
            return t0 + frac * (t1 - t0)
    return checkpoints[-1][1]


def scale_checkpoints(checkpoints: Sequence[Tuple[float, float]], factor: float) -> List[Tuple[float, float]]:
    return [(d * factor, t) for d, t in checkpoints]


def _drop_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# ---------------------------------------------------------------------------
# Ravitos (voir ASSUMPTIONS["aid_stations"])
# ---------------------------------------------------------------------------

def detect_stops(samples: Sequence[dict], *,
                  speed_threshold_ms: float = STOP_SPEED_MS_THRESHOLD,
                  min_duration_s: float = STOP_MIN_DURATION_S) -> List[Tuple[float, float, float]]:
    """Rend une liste `(distance_m milieu, t_s début, durée_s)` pour chaque
    intervalle soutenu de vitesse quasi nulle dans `samples` (triés par `t_s`,
    champs `t_s`/`distance_m`/`speed_ms` — format normalisé, voir
    `tests/README.md` section échantillons). Un trou de vitesse manquante
    coupe l'intervalle en cours (jamais supposée nulle)."""
    ordered = sorted((s for s in samples if s.get("speed_ms") is not None), key=lambda s: s["t_s"])
    stops = []
    start = None
    for s in ordered:
        if s["speed_ms"] < speed_threshold_ms:
            if start is None:
                start = s
        else:
            if start is not None:
                duration = s["t_s"] - start["t_s"]
                if duration >= min_duration_s:
                    mid_m = (start.get("distance_m", 0.0) + s.get("distance_m", start.get("distance_m", 0.0))) / 2.0
                    stops.append((mid_m, start["t_s"], duration))
                start = None
    if start is not None and ordered:
        last = ordered[-1]
        duration = last["t_s"] - start["t_s"]
        if duration >= min_duration_s:
            stops.append((start.get("distance_m", 0.0), start["t_s"], duration))
    return stops


def aid_station_times(plan_aid_stations: Sequence[dict], samples: Sequence[dict],
                       *, sample_scale_factor: float = 1.0) -> List[dict]:
    """Associe à chaque ravito du plan (`{"km", "name", ...}`) l'arrêt détecté
    dans `samples` le plus proche (à moins de `AID_STATION_MATCH_RADIUS_M`,
    distance des échantillons mise à l'échelle par `sample_scale_factor` —
    même logique que les splits, voir `ASSUMPTIONS["alignment"]`). Un ravito
    sans arrêt détecté à proximité n'apparaît PAS dans le résultat (jamais une
    durée devinée)."""
    stops = detect_stops(samples)
    scaled_stops = [(m * sample_scale_factor, t, dur) for m, t, dur in stops]
    out = []
    for station in plan_aid_stations:
        km = station.get("km")
        if km is None:
            continue
        target_m = km * 1000.0
        best = None
        for mid_m, _t, dur in scaled_stops:
            if abs(mid_m - target_m) <= AID_STATION_MATCH_RADIUS_M and (best is None or dur > best):
                best = dur
        if best is not None:
            out.append({"km": km, "name": station.get("name"), "actual_stop_s": round(best, 1)})
    return out


# ---------------------------------------------------------------------------
# Assemblage principal
# ---------------------------------------------------------------------------

def build_race_debrief(plan: dict, activity: dict, *,
                        scenario: str = DEFAULT_SCENARIO,
                        carbs_target_g_h: Optional[float] = None,
                        carbs_actual_g_h: Optional[float] = None,
                        carbs_ceiling_g_h: Optional[float] = None,
                        planned_weather: Optional[dict] = None,
                        actual_weather: Optional[dict] = None,
                        fit_samples: Optional[Sequence[dict]] = None) -> dict:
    """Assemble le débrief complet plan vs réalisé — pure (aucun accès disque),
    pour que la CLI et les tests partagent le même chemin de calcul.

    Lève `DebriefError` si le plan n'a pas de `segments` (#59 requis) ou si
    l'activité n'a pas de `splits` exploitables."""
    segments = sorted(plan.get("segments") or [], key=lambda s: s["km_start"])
    if not segments:
        raise DebriefError(
            "planning sans `segments` (#59, scripts/arc_race_pacing.py) : impossible de débriefer par "
            "segment — le plan doit avoir été construit à partir d'un GPX"
        )

    checkpoints = build_actual_checkpoints(activity)
    plan_total_m = segments[-1]["km_end"] * 1000.0
    actual_total_m = checkpoints[-1][0]
    if plan_total_m <= 0 or actual_total_m <= 0:
        raise DebriefError("distance totale du plan ou de l'activité nulle : rien à aligner")

    scale_factor = plan_total_m / actual_total_m
    mismatch_pct = abs(actual_total_m - plan_total_m) / plan_total_m * 100.0
    scaled_checkpoints = scale_checkpoints(checkpoints, scale_factor)

    warnings: List[str] = []
    if mismatch_pct > DISTANCE_MISMATCH_WARN_PCT:
        warnings.append(
            f"distance mesurée de l'activité ({actual_total_m / 1000.0:.2f} km) et distance du plan "
            f"({plan_total_m / 1000.0:.2f} km) diffèrent de {mismatch_pct:.1f} % : les splits ont été "
            "mis à l'échelle proportionnellement sur la distance cumulée (jamais sur le temps) pour "
            "s'aligner sur le référentiel du plan — voir ASSUMPTIONS['alignment']."
        )

    segment_debriefs = []
    cumulative_planned_s = 0.0
    all_planned_known = True
    weighted_first_third_delta_num = 0.0
    weighted_first_third_delta_den = 0.0
    for seg in segments:
        km_start_m = seg["km_start"] * 1000.0
        km_end_m = seg["km_end"] * 1000.0
        t_start = _interpolate_cum_time(scaled_checkpoints, km_start_m)
        t_end = _interpolate_cum_time(scaled_checkpoints, km_end_m)
        actual_time_s = t_end - t_start
        distance_km = (km_end_m - km_start_m) / 1000.0
        actual_pace_s_km = actual_time_s / distance_km if distance_km > 0 else None

        predicted = (seg.get("predicted_time_s") or {}).get(scenario)
        planned_pace = (seg.get("pace_s_km") or {}).get(scenario)

        entry = {
            "id": seg["id"], "km_start": seg["km_start"], "km_end": seg["km_end"],
            "distance_m": seg.get("distance_m"),
            "actual_time_s": round(actual_time_s, 1),
            "actual_pace_s_km": round(actual_pace_s_km, 1) if actual_pace_s_km is not None else None,
            "planned_time_s": predicted,
            "planned_pace_s_km": planned_pace,
        }
        if predicted is not None:
            delta_s = actual_time_s - predicted
            entry["delta_s"] = round(delta_s, 1)
            entry["delta_pct"] = round(delta_s / predicted * 100.0, 1) if predicted else None
            cumulative_planned_s += predicted
            entry["cumulative_drift_s"] = round(t_end - cumulative_planned_s, 1)
            if km_end_m <= plan_total_m * FAST_START_FRACTION + 1e-6:
                weighted_first_third_delta_num += entry["delta_pct"] * distance_km
                weighted_first_third_delta_den += distance_km
        else:
            all_planned_known = False
        segment_debriefs.append(_drop_none(entry))

    total_actual_s = scaled_checkpoints[-1][1]
    totals = {"actual_time_s": round(total_actual_s, 1)}
    if all_planned_known and cumulative_planned_s > 0:
        totals["planned_time_s"] = round(cumulative_planned_s, 1)
        totals["delta_s"] = round(total_actual_s - cumulative_planned_s, 1)
        totals["delta_pct"] = round(totals["delta_s"] / cumulative_planned_s * 100.0, 1)
    elif cumulative_planned_s > 0:
        totals["planned_time_s_partial"] = round(cumulative_planned_s, 1)
        warnings.append(
            "un ou plusieurs segments du plan n'ont pas de `predicted_time_s` pour le scénario "
            f"{scenario!r} : le temps planifié total est partiel, la dérive cumulée n'est pas fiable "
            "au-delà du dernier segment chiffré."
        )

    fade = _compute_fade(segments, scaled_checkpoints, plan_total_m, scenario)

    carbs = {}
    resolved_actual_carbs = carbs_actual_g_h
    if resolved_actual_carbs is None:
        resolved_actual_carbs = M.carbs_per_hour_g(activity)
    if resolved_actual_carbs is not None:
        carbs["actual_g_h"] = round(resolved_actual_carbs, 1)
    if carbs_target_g_h is not None:
        carbs["planned_g_h"] = round(carbs_target_g_h, 1)
    if "actual_g_h" in carbs and "planned_g_h" in carbs and carbs["planned_g_h"]:
        carbs["delta_g_h"] = round(carbs["actual_g_h"] - carbs["planned_g_h"], 1)
        carbs["delta_pct"] = round(carbs["delta_g_h"] / carbs["planned_g_h"] * 100.0, 1)

    weather = {}
    if actual_weather:
        weather["actual"] = _weather_subset(actual_weather)
    if planned_weather:
        weather["planned"] = _weather_subset(planned_weather)

    aid_times = None
    if fit_samples is not None:
        aid_times = aid_station_times(plan.get("aid_stations") or [], fit_samples,
                                       sample_scale_factor=scale_factor)

    findings, suggested_profile_updates = _build_findings(
        weighted_first_third_delta_num, weighted_first_third_delta_den, fade,
        carbs, carbs_ceiling_g_h, totals, segment_debriefs,
    )

    result = {
        "race_name": plan.get("race_name"),
        "race_date": plan.get("race_date"),
        "scenario": scenario,
        "segments": segment_debriefs,
        "totals": totals,
        "alignment": {
            "plan_distance_m": round(plan_total_m, 1),
            "actual_distance_m": round(actual_total_m, 1),
            "scale_factor": round(scale_factor, 4),
            "mismatch_pct": round(mismatch_pct, 2),
        },
        "findings": findings,
        "suggested_profile_updates": suggested_profile_updates,
        "warnings": warnings,
    }
    if fade:
        result["fade"] = fade
    if carbs:
        result["carbs"] = carbs
    if weather:
        result["weather"] = weather
    if aid_times is not None:
        result["aid_station_times"] = aid_times
    return _drop_none(result)


def _weather_subset(weather: dict) -> dict:
    keys = ("temp_min_c", "temp_max_c", "feels_like_c", "humidity_pct", "wind_kmh", "category")
    return {k: weather[k] for k in keys if k in weather and weather[k] is not None}


def _compute_fade(segments: Sequence[dict], scaled_checkpoints: Sequence[Tuple[float, float]],
                   plan_total_m: float, scenario: str) -> dict:
    """Voir `ASSUMPTIONS["fade"]`. Rend un dict vide si les segments du plan
    n'ont pas tous un `predicted_time_s` pour `scenario` (rien à comparer côté
    plan) — le fade RÉEL seul, sans référence, n'a pas de sens à publier ici."""
    half_m = plan_total_m * FADE_HALF_FRACTION
    t_half_actual = _interpolate_cum_time(scaled_checkpoints, half_m)
    t_end_actual = scaled_checkpoints[-1][1]
    pace_first_half_actual = t_half_actual / (half_m / 1000.0) if half_m > 0 else None
    pace_second_half_actual = (
        (t_end_actual - t_half_actual) / (half_m / 1000.0) if half_m > 0 else None
    )
    fade: Dict[str, float] = {}
    if pace_first_half_actual and pace_first_half_actual > 0:
        fade["actual_pct"] = round(
            (pace_second_half_actual - pace_first_half_actual) / pace_first_half_actual * 100.0, 1)

    planned_checkpoints: List[Tuple[float, float]] = [(0.0, 0.0)]
    cum = 0.0
    for seg in segments:
        predicted = (seg.get("predicted_time_s") or {}).get(scenario)
        if predicted is None:
            return _drop_none(fade) if "actual_pct" in fade else {}
        cum += predicted
        planned_checkpoints.append((seg["km_end"] * 1000.0, cum))

    t_half_planned = _interpolate_cum_time(planned_checkpoints, half_m)
    t_end_planned = planned_checkpoints[-1][1]
    pace_first_half_planned = t_half_planned / (half_m / 1000.0) if half_m > 0 else None
    pace_second_half_planned = (
        (t_end_planned - t_half_planned) / (half_m / 1000.0) if half_m > 0 else None
    )
    if pace_first_half_planned and pace_first_half_planned > 0:
        fade["planned_pct"] = round(
            (pace_second_half_planned - pace_first_half_planned) / pace_first_half_planned * 100.0, 1)
        if "actual_pct" in fade:
            fade["vs_plan_pct"] = round(fade["actual_pct"] - fade["planned_pct"], 1)
    return fade


def _build_findings(first_third_num: float, first_third_den: float, fade: dict,
                     carbs: dict, carbs_ceiling_g_h: Optional[float], totals: dict,
                     segment_debriefs: Sequence[dict]) -> Tuple[List[dict], List[dict]]:
    findings: List[dict] = []
    suggested: List[dict] = []

    if "delta_pct" in totals:
        findings.append({
            "code": "ecart_temps_total",
            "severity": "info",
            "message": f"Temps total réalisé {totals['delta_pct']:+.1f} % vs plan "
                       f"({'plus rapide' if totals['delta_pct'] < 0 else 'plus lent'} que prévu).",
        })

    if first_third_den > 0 and "vs_plan_pct" in fade:
        avg_first_third_pct = first_third_num / first_third_den
        if avg_first_third_pct <= FAST_START_DELTA_PCT_THRESHOLD and \
                fade["vs_plan_pct"] >= FAST_START_FADE_EXCESS_PCT_THRESHOLD:
            findings.append({
                "code": "depart_trop_rapide",
                "severity": "warning",
                "message": (
                    f"Premier tiers de course {abs(avg_first_third_pct):.1f} % plus rapide que le plan, "
                    f"suivi d'un fade {fade['vs_plan_pct']:+.1f} points au-delà de celui déjà anticipé "
                    "par le plan : probable lien de cause à effet."
                ),
                "segments": [s["id"] for s in segment_debriefs
                             if s.get("delta_pct") is not None and s["delta_pct"] <= FAST_START_DELTA_PCT_THRESHOLD],
            })
            suggested.append({
                "field": "Préférences de coaching",
                "suggestion": "Ajouter une consigne d'allure de départ plus prudente sur les prochaines "
                               "courses (tendance à partir trop vite observée sur ce débrief).",
                "rationale": "depart_trop_rapide",
                "status": "proposed",
            })

    actual_g_h, planned_g_h = carbs.get("actual_g_h"), carbs.get("planned_g_h")
    if actual_g_h is not None and planned_g_h:
        if actual_g_h < planned_g_h * (1 - CARBS_UNDER_TARGET_TOLERANCE_PCT / 100.0):
            findings.append({
                "code": "glucides_sous_objectif",
                "severity": "warning",
                "message": f"Glucides réalisés ({actual_g_h:g} g/h) sous l'objectif ({planned_g_h:g} g/h) "
                           f"de plus de {CARBS_UNDER_TARGET_TOLERANCE_PCT:g} %.",
            })
    if actual_g_h is not None and carbs_ceiling_g_h and actual_g_h > carbs_ceiling_g_h:
        findings.append({
            "code": "glucides_au_dessus_plafond",
            "severity": "info",
            "message": f"Glucides réalisés ({actual_g_h:g} g/h) au-dessus du plafond connu "
                       f"({carbs_ceiling_g_h:g} g/h) — sans incident signalé ailleurs, jamais une preuve "
                       "de tolérance digestive.",
        })
        suggested.append({
            "field": "objectif glucides/h (entraînement digestif, #41)",
            "suggestion": f"Envisager de relever le plafond glucides/h au-delà de {carbs_ceiling_g_h:g} g/h "
                          f"— {actual_g_h:g} g/h ingérés sans incident signalé sur cette course.",
            "rationale": "glucides_au_dessus_plafond",
            "status": "proposed",
        })

    return findings, suggested


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Débrief post-course : plan vs réalisé, par segment (#61).")
    ap.add_argument("command", choices=("debrief",), help="sous-commande (seule « debrief » existe)")
    ap.add_argument("--plan", required=True, type=Path, help="fichier plan de course (kind: race_plan)")
    ap.add_argument("--activity", required=True, type=Path, help="fichier activité de la course (kind: activity)")
    ap.add_argument("--scenario", choices=("safe", "realistic", "ambitious"), default=DEFAULT_SCENARIO,
                     help="scénario du plan utilisé comme référence (défaut realistic)")
    ap.add_argument("--carbs-target-g-h", type=float, dest="carbs_target_g_h",
                     help="objectif glucides/h du plan nutrition (aucun champ structuré ne le porte, #61)")
    ap.add_argument("--carbs-actual-g-h", type=float, dest="carbs_actual_g_h",
                     help="débit glucides/h réalisé, si connu autrement que par activity.carbs_g/duration_s")
    ap.add_argument("--carbs-ceiling-g-h", type=float, dest="carbs_ceiling_g_h",
                     help="plafond glucides/h connu (scripts/arc_index.py fueling, carbs_ceiling_g_h)")
    ap.add_argument("--planned-weather", type=Path, dest="planned_weather",
                     help="fichier météo (kind: weather) prévue au moment du plan")
    ap.add_argument("--actual-weather", type=Path, dest="actual_weather",
                     help="fichier météo (kind: weather) réelle du jour de course")
    ap.add_argument("--fit", type=Path, help="fichier d'échantillons FIT (#42) pour détecter les arrêts ravito")
    return ap


def _load_fit_samples(path: Optional[Path]) -> Optional[List[dict]]:
    if path is None:
        return None
    if not path.exists():
        raise DebriefError(f"fichier FIT introuvable : {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        samples = data.get("samples") or data.get("records") or []
    elif isinstance(data, list):
        samples = data
    else:
        samples = []
    return samples


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        plan = load_block(args.plan, expected_kind="race_plan")
        activity = load_block(args.activity, expected_kind="activity")
        planned_weather = load_block(args.planned_weather, expected_kind="weather") if args.planned_weather else None
        actual_weather = load_block(args.actual_weather, expected_kind="weather") if args.actual_weather else None
        fit_samples = _load_fit_samples(args.fit)
        debrief = build_race_debrief(
            plan, activity, scenario=args.scenario,
            carbs_target_g_h=args.carbs_target_g_h, carbs_actual_g_h=args.carbs_actual_g_h,
            carbs_ceiling_g_h=args.carbs_ceiling_g_h,
            planned_weather=planned_weather, actual_weather=actual_weather,
            fit_samples=fit_samples,
        )
    except DebriefError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    print(json.dumps(debrief, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
