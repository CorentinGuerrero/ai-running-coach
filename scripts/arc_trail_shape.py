#!/usr/bin/env python3
"""Score « Trail Shape » (#63, épopée #23) : préparation à l'objectif actif.

## Principe

Runalyze propose un « Marathon Shape » (volume + sortie longue vs une course
route). L'équivalent trail posé ici compare, sur les `TRAIL_SHAPE_WINDOW_WEEKS`
dernières semaines glissantes, ce que l'athlète a RÉELLEMENT couru à ce
qu'exige la course visée (`planning/active_objective.md` : distance, D+,
date) — jamais l'inverse (aucune prescription de plan ici, seulement un état
des lieux).

Quatre composantes, chacune avec une cible EXPLICITE dérivée des exigences de
la course, une valeur RÉELLEMENT observée sur la fenêtre, et un ratio
observé/cible plafonné à 100 % :

1. **Volume hebdomadaire** (`weekly_volume`) : moyenne du km-effort ITRA
   (`arc_metrics.effort_km_itra`, #35 — distance + D+/100, seul KPI du projet
   qui compte le D+ dans un volume hebdomadaire) sur la fenêtre, comparée à
   une cible = km-effort de la course × `WEEKLY_VOLUME_TARGET_RATIO`.
2. **Plus longue sortie** (`longest_run`) : distance de la plus longue sortie
   de la fenêtre, comparée à une cible dérivée de la distance de course (voir
   `LONG_RUN_FULL_DISTANCE_CAP_M`/`LONG_RUN_RATIO_BEYOND_CAP`).
3. **D+ max d'une séance** (`max_dplus`) : dénivelé positif de la séance la
   plus « montante » de la fenêtre, comparée à une cible = D+ de la course ×
   `MAX_DPLUS_SESSION_RATIO`. OMISE si la course n'a pas de D+ renseigné
   (route) — une course plate n'a pas de cible de D+ par séance qui aurait un
   sens.
4. **Durabilité** (`durability`, #48) : fade GAP moyen sur les sorties
   longues éligibles de la fenêtre (`arc_metrics.durability_trend`), converti
   en ratio « moins on fade, mieux c'est ». OMISE si aucune sortie longue de
   la fenêtre n'est éligible (voir `arc_durability.ASSUMPTIONS` pour les
   raisons structurelles d'inéligibilité — jamais un bug).

Le score global est la moyenne pondérée des ratios des composantes
ÉLIGIBLES, poids RENORMALISÉS à 1.0 sur les composantes présentes (une
composante omise ne pénalise jamais le score — elle est absente du calcul,
pas comptée à 0). `notes`/`data_confidence` rapportent toujours POURQUOI une
composante est absente ou pourquoi la confiance est réduite (jamais une
omission silencieuse).

## Sur les constantes ci-dessous (honnêteté du repère)

**Aucune des constantes `*_RATIO`/`*_CAP` ci-dessous ne vient d'une source
publiée et vérifiable** — contrairement à `effort_km_itra` (méthode ITRA
publiée, voir `arc_metrics.py`), il n'existe pas de littérature qui chiffre
« la cible de volume hebdomadaire est X % de l'effort de course ». Ce sont
des **approximations du projet**, du bon sens d'entraînement (une semaine de
volume à ~50 % de la distance de course, une plus longue sortie plafonnée
au-delà du marathon, un D+ de sortie à une fraction du D+ de course) rendues
explicites et ajustables ICI, jamais des chiffres à présenter comme validés
scientifiquement. Quiconque n'est pas d'accord peut changer une constante et
relancer `arc_index.py trail-shape` — c'est tout l'intérêt de les sortir en
tête de module plutôt que de les enfouir dans le calcul.

## Ce que le score NE fait PAS

- Ne recalcule rien : `effort_km_itra`/`durability_trend` viennent de
  `arc_metrics.py`, jamais réimplémentés ici (#35, #48).
- N'utilise AUCUNE donnée de santé (HRV, FC de repos, readiness,
  `[health].morning_check`) : un score de préparation basé sur l'historique
  d'entraînement, pas un verdict du jour — voir `agents/coach.md` pour
  comment il doit être présenté (un indicateur parmi d'autres, jamais un
  verdict).
- Ne prescrit rien : pas de plan de rattrapage, pas de recommandation de
  séance. Un état des lieux, à charge du coach (ou de l'athlète) d'en tirer
  des conséquences.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

import arc_metrics as M

# ---------------------------------------------------------------------------
# Constantes réglables (voir la docstring du module : approximations du
# projet, PAS de la littérature vérifiée, sauf mention contraire explicite)
# ---------------------------------------------------------------------------

# Fenêtre d'observation : 6-8 semaines glissantes par #63 — 8 choisies (borne
# haute) pour lisser une semaine de repos ou de voyage isolée, même esprit que
# les fenêtres de tendance FIT du projet (12 semaines pour le découplage/#45,
# la VAM/#46, la descente/#47, la durabilité/#48 — plus courte ici car le
# volume hebdomadaire, contrairement à ces tendances physiologiques, doit
# refléter le bloc d'entraînement RÉCENT, pas une demi-année).
TRAIL_SHAPE_WINDOW_WEEKS = 8

# En dessous de ce nombre de semaines distinctes AVEC au moins une séance de
# la famille course à pied dans la fenêtre, la confiance du score est
# rapportée "low" (donnée éparse, #63) — jamais un blocage, juste un
# avertissement explicite dans la sortie.
TRAIL_SHAPE_MIN_WEEKS_WITH_DATA = 4

# En dessous de cette distance de course, les cibles d'endurance ci-dessous
# (pensées pour une préparation de plusieurs semaines) n'ont plus de sens —
# approximation du projet, pas une frontière physiologique nette.
TRAIL_SHAPE_MIN_DISTANCE_M = 5000

# Au-delà de cet horizon, le bloc spécifique n'a probablement pas commencé :
# le score reste calculé (utile pour suivre une tendance), mais annoté d'une
# note explicite plutôt que présenté comme un verdict de préparation.
TRAIL_SHAPE_FAR_HORIZON_WEEKS = 26

# Cible de volume hebdomadaire (km-effort ITRA, #35) = km-effort de la course
# × ce ratio. Approximation du projet : une semaine-type de fin de
# préparation qui couvre environ la moitié de l'effort de course est un
# repère d'entraînement courant en trail/ultra, jamais une norme publiée.
WEEKLY_VOLUME_TARGET_RATIO = 0.5

# Cible de plus longue sortie : jusqu'au marathon, courir la distance de
# course en entraînement reste courant (cible = distance de course) ;
# au-delà (ultra), la cible plafonne à une fraction de la distance de course
# — personne ne court un 100 km à l'entraînement. Approximations du projet.
LONG_RUN_FULL_DISTANCE_CAP_M = 42195.0
LONG_RUN_RATIO_BEYOND_CAP = 0.6

# Cible de D+ max d'une séance = D+ de la course × ce ratio. Approximation du
# projet : une sortie qui couvre environ la moitié du D+ de course prépare la
# tolérance à la descente/montée répétée, sans exiger de reproduire la course
# entière en une séance.
MAX_DPLUS_SESSION_RATIO = 0.5

# Fade GAP (#48, `arc_metrics.durability_trend`) au-delà duquel le ratio de
# durabilité tombe à 0 — un fade nul ou négatif (négative splitting) donne un
# ratio de 1.0. Approximation du projet, pas un seuil clinique (voir
# `arc_durability.ASSUMPTIONS["model"]` : la durabilité elle-même n'est
# « qu'un repère de coaching indicatif »).
DURABILITY_MAX_ACCEPTABLE_FADE_PCT = 15.0

# Poids de chaque composante dans le score global, AVANT renormalisation sur
# les composantes éligibles (voir la docstring du module). Somme = 1.0.
COMPONENT_WEIGHTS = {
    "weekly_volume": 0.35,
    "longest_run": 0.30,
    "max_dplus": 0.20,
    "durability": 0.15,
}

COMPONENT_LABELS = {
    "weekly_volume": "Volume hebdomadaire (km-effort)",
    "longest_run": "Plus longue sortie",
    "max_dplus": "D+ max d'une séance",
    "durability": "Durabilité (fade GAP, sorties longues)",
}

FORMULA_TEXT = (
    "Score = Σ(ratio_composante × poids_renormalisé) × 100, ratio de chaque composante "
    "= min(1.0, valeur_observée / cible), poids renormalisés à 1.0 sur les seules "
    "composantes éligibles (voir COMPONENT_WEIGHTS, arc_trail_shape.py)."
)


def _race_effort_km(distance_m: float, elevation_gain_m: Optional[float]) -> float:
    """Km-effort ITRA (#35) de la course elle-même — même formule que
    `arc_metrics.effort_km_itra_raw`, appliquée à la course plutôt qu'à une
    séance réalisée (jamais réimplémentée : on construit une activité de
    circonstance pour rester sur l'unique implémentation de la formule)."""
    fake = {"sport": "trail", "distance_m": distance_m, "elevation_gain_m": elevation_gain_m or 0}
    return M.effort_km_itra_raw(fake) or 0.0


def _iso_week(iso_date: str) -> tuple:
    y, w, _ = date.fromisoformat(iso_date).isocalendar()
    return (y, w)


def _component(id_: str, target: Optional[float], actual: Optional[float], unit: str,
                ratio: Optional[float], eligible: bool, reason: Optional[str] = None) -> dict:
    return {
        "id": id_,
        "label": COMPONENT_LABELS[id_],
        "target": round(target, 1) if target is not None else None,
        "actual": round(actual, 1) if actual is not None else None,
        "unit": unit,
        "ratio": round(ratio, 3) if ratio is not None else None,
        "weight": COMPONENT_WEIGHTS[id_],
        "eligible": eligible,
        "reason": reason,
    }


def trail_shape_report(objective: Optional[dict], activities: List[dict], today: date,
                        window_weeks: int = TRAIL_SHAPE_WINDOW_WEEKS) -> dict:
    """Rapport « Trail Shape » (#63) pour l'objectif actif.

    `objective` : dict issu de `arc_legacy.parse_objective`/table `objective`
    (au moins `race_date` ; `distance_m`/`elevation_gain_m` idéalement), ou
    `None`/vide si `planning/active_objective.md` est absent ou vide.
    `activities` : dicts portant au moins `date` (AAAA-MM-JJ), `sport`,
    `distance_m`, `elevation_gain_m` ; `duration_s`/`moving_duration_s`/
    `durability_gap_fade_pct`/`durability_reason`/`durability_reason_code`
    optionnels (nécessaires pour la composante durabilité, voir
    `arc_metrics.durability_trend`) — mêmes clés que les autres tendances du
    projet, aucune transformation supplémentaire attendue de l'appelant.

    Rend toujours `status` (voir les valeurs ci-dessous) et `score` (`None`
    hors `status == "ok"`). AUCUNE donnée de santé consultée ici — voir la
    docstring du module."""
    base = {"status": None, "score": None, "objective": None, "window_weeks": window_weeks,
            "data_confidence": None, "weeks_with_data": None, "notes": [], "components": [],
            "formula": FORMULA_TEXT}

    if not objective or not objective.get("race_date"):
        return {**base, "status": "no_objective",
                "notes": ["Aucun objectif actif : planning/active_objective.md est absent, vide, ou "
                          "sans date de course renseignée."]}

    race_date = date.fromisoformat(objective["race_date"])
    distance_m = objective.get("distance_m")
    elevation_gain_m = objective.get("elevation_gain_m")
    days_left = (race_date - today).days
    obj_out = {"name": objective.get("name"), "race_date": objective["race_date"],
               "distance_m": distance_m, "elevation_gain_m": elevation_gain_m, "days_left": days_left}

    if distance_m is None:
        return {**base, "status": "incomplete_objective", "objective": obj_out,
                "notes": ["Distance de course absente de planning/active_objective.md : les cibles "
                          "ne peuvent pas être calculées."]}

    if days_left < 0:
        return {**base, "status": "race_past", "objective": obj_out,
                "notes": [f"La course est passée ({-days_left} jour(s)) : le score de préparation "
                          "n'a plus d'objet — voir plutôt un débrief post-course."]}

    if distance_m < TRAIL_SHAPE_MIN_DISTANCE_M:
        return {**base, "status": "race_too_short", "objective": obj_out,
                "notes": [f"Distance de course ({distance_m:.0f} m) sous le plancher "
                          f"({TRAIL_SHAPE_MIN_DISTANCE_M:.0f} m, arc_trail_shape.TRAIL_SHAPE_MIN_DISTANCE_M) : "
                          "les cibles de volume/sortie longue de ce score visent une préparation "
                          "d'endurance de plusieurs semaines, pas une course courte."]}

    notes: List[str] = []
    if days_left / 7 > TRAIL_SHAPE_FAR_HORIZON_WEEKS:
        notes.append(f"Objectif à {days_left / 7:.0f} semaines : le bloc spécifique n'a probablement pas "
                     "commencé, ce score reflète la forme ACTUELLE, pas le pic prévu pour la course.")

    window_start = today - timedelta(days=window_weeks * 7 - 1)
    run_activities = [a for a in activities
                      if a.get("date") and M.sport_family(a.get("sport")) == "run"
                      and window_start.isoformat() <= a["date"] <= today.isoformat()]

    weeks_with_data = len({_iso_week(a["date"]) for a in run_activities})
    data_confidence = "low" if weeks_with_data < TRAIL_SHAPE_MIN_WEEKS_WITH_DATA else "normal"
    if data_confidence == "low":
        notes.append(f"Seulement {weeks_with_data} semaine(s) avec au moins une séance de course à pied "
                     f"sur les {window_weeks} de la fenêtre (seuil {TRAIL_SHAPE_MIN_WEEKS_WITH_DATA}) : "
                     "confiance réduite, moyenne diluée par les semaines sans donnée.")

    race_effort_km = _race_effort_km(distance_m, elevation_gain_m)

    # 1) Volume hebdomadaire (#35)
    total_effort_km = M.effort_km_week_total(run_activities)
    avg_weekly_effort_km = total_effort_km / window_weeks
    weekly_target = race_effort_km * WEEKLY_VOLUME_TARGET_RATIO
    weekly_ratio = min(1.0, avg_weekly_effort_km / weekly_target) if weekly_target > 0 else None
    components = [_component("weekly_volume", weekly_target, avg_weekly_effort_km, "km",
                              weekly_ratio, weekly_ratio is not None)]

    # 2) Plus longue sortie
    distances = [a["distance_m"] for a in run_activities if a.get("distance_m")]
    longest_m = max(distances) if distances else 0.0
    long_target = (distance_m if distance_m <= LONG_RUN_FULL_DISTANCE_CAP_M
                   else distance_m * LONG_RUN_RATIO_BEYOND_CAP)
    long_ratio = min(1.0, longest_m / long_target) if long_target > 0 else None
    components.append(_component("longest_run", long_target, longest_m, "m", long_ratio, long_ratio is not None))

    # 3) D+ max d'une séance — omise sans D+ de course (route)
    if elevation_gain_m and elevation_gain_m > 0:
        dplus_values = [a.get("elevation_gain_m") or 0 for a in run_activities]
        max_dplus = max(dplus_values) if dplus_values else 0.0
        dplus_target = elevation_gain_m * MAX_DPLUS_SESSION_RATIO
        dplus_ratio = min(1.0, max_dplus / dplus_target) if dplus_target > 0 else None
        components.append(_component("max_dplus", dplus_target, max_dplus, "m", dplus_ratio,
                                      dplus_ratio is not None))
    else:
        components.append(_component("max_dplus", None, None, "m", None, False,
                                      "course sans D+ renseigné (route) : cible de D+ par séance sans objet"))

    # 4) Durabilité (#48) — omise si aucune sortie longue éligible sur la fenêtre
    trend = M.durability_trend(activities, today, window_weeks)
    if trend["measured_n"] > 0:
        fade = trend["avg_gap_fade_pct"]
        durability_ratio = max(0.0, min(1.0, 1 - fade / DURABILITY_MAX_ACCEPTABLE_FADE_PCT))
        components.append(_component("durability", DURABILITY_MAX_ACCEPTABLE_FADE_PCT, fade, "% fade GAP",
                                      durability_ratio, True))
    else:
        reason = trend.get("dominant_reason") or (
            f"aucune sortie longue (> {M.LONG_RUN_MIN_DURATION_S // 60} min) sur la fenêtre"
            if trend["long_runs"] == 0 else "aucune sortie longue éligible sur la fenêtre")
        components.append(_component("durability", None, None, "% fade GAP", None, False, reason))
        notes.append(f"Durabilité non intégrée au score : {reason} — poids redistribué sur les autres "
                     "composantes.")

    eligible = [c for c in components if c["eligible"]]
    weight_sum = sum(c["weight"] for c in eligible)
    score = None
    if eligible and weight_sum > 0:
        score = round(sum(c["ratio"] * (c["weight"] / weight_sum) for c in eligible) * 100, 1)
        for c in eligible:
            c["weight_renormalized"] = round(c["weight"] / weight_sum, 3)
        for c in components:
            if not c["eligible"]:
                c["weight_renormalized"] = 0.0

    return {**base, "status": "ok", "score": score, "objective": obj_out,
            "data_confidence": data_confidence, "weeks_with_data": weeks_with_data,
            "notes": notes, "components": components}
