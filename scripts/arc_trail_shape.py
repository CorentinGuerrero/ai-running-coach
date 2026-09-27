#!/usr/bin/env python3
"""Score « Trail Shape » (#63, épopée #23) : préparation à l'objectif actif.

## Principe

Runalyze propose un « Marathon Shape » (volume + sortie longue vs une course
route). L'équivalent trail posé ici compare, sur les `TRAIL_SHAPE_WINDOW_WEEKS`
(8) dernières semaines glissantes, ce que l'athlète a RÉELLEMENT couru à ce
qu'exige la course visée (`planning/active_objective.md` : distance, D+,
date) — jamais l'inverse (aucune prescription de plan ici, seulement un état
des lieux).

Quatre composantes, chacune avec une cible EXPLICITE dérivée des exigences de
la course, une valeur RÉELLEMENT observée sur la fenêtre, et un ratio
observé/cible plafonné à 100 % :

1. **Volume hebdomadaire** (`weekly_volume`) : moyenne du km-effort ITRA
   (`arc_metrics.effort_km_itra`, #35 — distance + D+/100, seul KPI du projet
   qui compte le D+ dans un volume hebdomadaire) sur la fenêtre, comparée à
   une cible SOUS-LINÉAIRE de l'effort de course (voir `weekly_volume_target_km`)
   — **course/trail uniquement** (`arc_metrics.RUNNING_SPORTS`), la randonnée
   et la marche n'étant pas un stimulus comparable pour un volume d'allure.
2. **Plus longue sortie** (`longest_run`) : distance de la plus longue sortie
   de la fenêtre — **course/trail uniquement**, même restriction que ci-dessus —
   comparée à une cible continue (voir `longest_run_target_m`).
3. **D+ max d'une séance** (`max_dplus`) : dénivelé positif de la séance la
   plus « montante » de la fenêtre, comparée à une cible = D+ de la course ×
   `MAX_DPLUS_SESSION_RATIO`, plafonnée à `MAX_DPLUS_TARGET_CAP_M`. **Inclut la
   randonnée/power-hiking** (`arc_metrics.sport_family(...) == "run"`),
   CONTRAIREMENT aux deux composantes ci-dessus : grimper en randonnée est une
   préparation légitime à la tolérance du dénivelé, même sans courir la
   portion. OMISE si la course n'a pas de D+ renseigné (route) ou un D+ nul.
4. **Durabilité** (`durability`, #48) : fade GAP moyen sur les sorties
   longues éligibles de la fenêtre (`arc_metrics.durability_trend`, qui
   applique SA PROPRE restriction interne — course/trail uniquement — jamais
   modifiée ici), converti en ratio « moins on fade, mieux c'est ». OMISE si
   aucune sortie longue de la fenêtre n'est éligible (voir
   `arc_durability.ASSUMPTIONS` pour les raisons structurelles
   d'inéligibilité — jamais un bug).

Le score global est la moyenne pondérée des ratios des composantes
ÉLIGIBLES, poids RENORMALISÉS à 1.0 sur les composantes présentes (une
composante omise ne pénalise jamais le score — elle est absente du calcul,
pas comptée à 0). `notes` rapporte toujours POURQUOI une composante est
absente ou pourquoi la confiance est réduite (jamais une omission
silencieuse) : chaque note est un objet `{"code", "message"}` — le code est
STABLE et destiné à piloter l'affichage (un appelant ne doit JAMAIS chercher
un mot français dans `message` pour décider quoi afficher, seul `code` fait
foi). Codes actuels : `far_horizon`, `low_confidence`, `durability_omitted`.

## L'activité du jour de course, si déjà loggée, est EXCLUE de la fenêtre

Si l'athlète lance ce score le jour même de sa course, APRÈS avoir déjà
persisté l'activité de la course (`date == objective.race_date`), cette
activité est retirée de tout calcul (volume, plus longue sortie, D+ max,
durabilité) — la course elle-même n'est pas une séance de PRÉPARATION, la
compter gonflerait artificiellement (souvent au maximum) les trois premières
composantes avec la performance qu'on cherche justement à évaluer en amont.
Cas rare en pratique (`status == "race_past"` bloque déjà tout score dès le
lendemain), mais explicite plutôt que silencieux.

## Sur les constantes ci-dessous (honnêteté du repère)

**Aucune des constantes `*_RATIO`/`*_CAP`/`*_FLOOR`/`*_SCALE` ci-dessous ne
vient d'une source publiée et vérifiable** — contrairement à `effort_km_itra`
(méthode ITRA publiée, voir `arc_metrics.py`), il n'existe pas de littérature
qui chiffre « la cible de volume hebdomadaire est X % de l'effort de course ».
Ce sont des **approximations du projet**, du bon sens d'entraînement rendues
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
- **Ne détecte AUCUN affûtage (taper)** : dans les 1-3 dernières semaines
  avant une course, une baisse VOLONTAIRE du volume est un signe de bonne
  préparation, pas d'un manque — mais ce module compare une moyenne BRUTE sur
  8 semaines à une cible fixe, sans réduire cette cible pendant l'affûtage.
  Un score qui baisse dans les toutes dernières semaines avant la course peut
  donc simplement refléter un affûtage réussi, jamais un signal d'alarme en
  soi à cette période — à lire avec le nombre de jours restants
  (`objective.days_left`) en tête.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

import arc_metrics as M

# ---------------------------------------------------------------------------
# Constantes réglables (voir la docstring du module : approximations du
# projet, PAS de la littérature vérifiée, sauf mention contraire explicite)
# ---------------------------------------------------------------------------

# Fenêtre d'observation : FIXE à 8 semaines glissantes (jamais "6 à 8" — un
# seul et même dénominateur partout, coach/vue/module) pour lisser une semaine
# de repos ou de voyage isolée, même esprit que les fenêtres de tendance FIT
# du projet (12 semaines pour le découplage/#45, la VAM/#46, la descente/#47,
# la durabilité/#48 — plus courte ici car le volume hebdomadaire, contrairement
# à ces tendances physiologiques, doit refléter le bloc d'entraînement RÉCENT,
# pas une demi-année).
TRAIL_SHAPE_WINDOW_WEEKS = 8

# En dessous de ce nombre de semaines distinctes AVEC au moins une séance de
# course à pied/trail dans la fenêtre, la confiance du score est rapportée
# "low" (donnée éparse, #63) — jamais un blocage, juste un avertissement
# explicite dans la sortie (note `low_confidence`).
TRAIL_SHAPE_MIN_WEEKS_WITH_DATA = 4

# En dessous de cette distance de course, les cibles d'endurance ci-dessous
# (pensées pour une préparation de plusieurs semaines) n'ont plus de sens —
# approximation du projet, pas une frontière physiologique nette.
TRAIL_SHAPE_MIN_DISTANCE_M = 5000

# Au-delà de cet horizon, le bloc spécifique n'a probablement pas commencé :
# le score reste calculé (utile pour suivre une tendance), mais annoté d'une
# note explicite (`far_horizon`) plutôt que présenté comme un verdict de
# préparation.
TRAIL_SHAPE_FAR_HORIZON_WEEKS = 26

# --- Volume hebdomadaire (km-effort ITRA, #35) ------------------------------
#
# Cible = clamp(WEEKLY_VOLUME_SCALE × √(km-effort de la course), floor, cap).
# Une simple proportion linéaire (ex. 50 % de l'effort de course) est
# TRIVIALE pour une course courte (un 10 km ne demande que 5 km/semaine à ce
# taux) et ABSURDE pour un ultra (un 170 km/10 000 D+ exigerait ~135
# km-effort/semaine, un volume de niveau élite) — cette courbe en RACINE
# CARRÉE (sous-linéaire par construction) monte plus vite pour les petites
# distances et s'aplatit pour les grandes, plafonnée par `WEEKLY_VOLUME_CAP_KM`
# pour ne jamais demander un volume hebdomadaire irréaliste, et plancher par
# `WEEKLY_VOLUME_FLOOR_KM` pour ne jamais tomber sous un volume d'endurance de
# base. Approximation du projet, calibrée à la main sur quelques repères
# (10 km ≈ 24 km-effort/semaine, marathon ≈ 49, ultra ≥ 100 km-effort de
# course → plafond 70 km-effort/semaine), jamais une norme publiée.
WEEKLY_VOLUME_SCALE = 7.5
WEEKLY_VOLUME_FLOOR_KM = 20.0
WEEKLY_VOLUME_CAP_KM = 70.0


def weekly_volume_target_km(race_effort_km: float) -> float:
    """Cible de volume hebdomadaire (km-effort ITRA) pour une course dont le
    km-effort total vaut `race_effort_km` — voir la note ci-dessus pour la
    justification de la courbe sous-linéaire (racine carrée) et de ses
    bornes."""
    if race_effort_km <= 0:
        return WEEKLY_VOLUME_FLOOR_KM
    raw = WEEKLY_VOLUME_SCALE * race_effort_km ** 0.5
    return max(WEEKLY_VOLUME_FLOOR_KM, min(raw, WEEKLY_VOLUME_CAP_KM))


# --- Plus longue sortie ------------------------------------------------------
#
# Cible = min(distance de course, clamp(LONG_RUN_TARGET_RATIO × distance,
# floor, cap)) — CONTINUE en distance de course, contrairement à une ancienne
# version qui plafonnait brutalement au-delà du marathon (42,195 km → cible =
# la distance elle-même ; 42,196 km → cible chutant à 60 % de la distance,
# une discontinuité de plusieurs kilomètres pour 1 m de plus). En dessous du
# plancher (`LONG_RUN_TARGET_FLOOR_M`, 30 km), le `min(...)` fait que la cible
# reste la distance de course elle-même (courir la distance en entraînement
# reste courant jusqu'à ~30 km) ; au-delà du plafond (`LONG_RUN_TARGET_CAP_M`,
# 60 km), la cible plafonne à 60 km quelle que soit la distance de course —
# personne ne court un 170 km à l'entraînement. Approximations du projet.
LONG_RUN_TARGET_RATIO = 0.6
LONG_RUN_TARGET_FLOOR_M = 30000.0
LONG_RUN_TARGET_CAP_M = 60000.0


def longest_run_target_m(distance_m: float) -> float:
    """Cible de plus longue sortie pour une course de `distance_m` — voir la
    note ci-dessus pour la continuité de la formule."""
    banded = max(LONG_RUN_TARGET_FLOOR_M, min(LONG_RUN_TARGET_RATIO * distance_m, LONG_RUN_TARGET_CAP_M))
    return min(distance_m, banded)


# --- D+ max d'une séance ------------------------------------------------------
#
# Cible = min(D+ de course × MAX_DPLUS_SESSION_RATIO, MAX_DPLUS_TARGET_CAP_M).
# Sans plafond absolu, un objectif à très fort D+ (ex. 10 000 m sur un
# multi-jours) exigerait une sortie à 5 000 m de D+ — hors de portée de la
# quasi-totalité des terrains d'entraînement accessibles. Approximations du
# projet.
MAX_DPLUS_SESSION_RATIO = 0.5
MAX_DPLUS_TARGET_CAP_M = 2500.0

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
    "weekly_volume": "Volume hebdomadaire (km-effort, course/trail)",
    "longest_run": "Plus longue sortie (course/trail)",
    "max_dplus": "D+ max d'une séance (course/trail/randonnée)",
    "durability": "Durabilité (fade GAP, sorties longues)",
}

# Unités des composantes — DISTINCTES entre distance et dénivelé (revue de
# code, blocage) : un appelant (l'UI) ne doit jamais formater un dénivelé
# comme une distance (1 250 m de D+ affiché "1,3 km" via un convertisseur de
# distance serait un contresens). `km_effort` : km-effort ITRA (#35), une
# grandeur composite (distance + D+/100), jamais convertie en miles/km comme
# une distance brute. `m_elevation` : mètres de dénivelé, jamais passés dans
# un convertisseur de distance. `m` : mètres de distance, convertibles en
# imperial. `pct_fade` : pourcentage de fade GAP (#48), sans conversion
# d'unité possible.
COMPONENT_UNITS = {
    "weekly_volume": "km_effort",
    "longest_run": "m",
    "max_dplus": "m_elevation",
    "durability": "pct_fade",
}

FORMULA_TEXT = (
    "Score = Σ(ratio_composante × poids_renormalisé) × 100, ratio de chaque composante "
    "= min(1.0, valeur_observée / cible), poids renormalisés à 1.0 sur les seules "
    "composantes éligibles (voir COMPONENT_WEIGHTS, arc_trail_shape.py)."
)


def _note(code: str, message: str) -> dict:
    return {"code": code, "message": message}


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


def _component(id_: str, target: Optional[float], actual: Optional[float],
                ratio: Optional[float], eligible: bool, reason: Optional[str] = None) -> dict:
    return {
        "id": id_,
        "label": COMPONENT_LABELS[id_],
        "target": round(target, 1) if target is not None else None,
        "actual": round(actual, 1) if actual is not None else None,
        "unit": COMPONENT_UNITS[id_],
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
    docstring du module. `notes` : liste d'objets `{"code", "message"}`, voir
    la docstring du module pour la liste des codes."""
    base = {"status": None, "score": None, "objective": None, "window_weeks": window_weeks,
            "data_confidence": None, "weeks_with_data": None, "notes": [], "components": [],
            "formula": FORMULA_TEXT}

    if not objective or not objective.get("race_date"):
        return {**base, "status": "no_objective",
                "notes": [_note("no_objective",
                                 "Aucun objectif actif : planning/active_objective.md est absent, vide, ou "
                                 "sans date de course renseignée.")]}

    race_date = date.fromisoformat(objective["race_date"])
    distance_m = objective.get("distance_m")
    elevation_gain_m = objective.get("elevation_gain_m")
    days_left = (race_date - today).days
    obj_out = {"name": objective.get("name"), "race_date": objective["race_date"],
               "distance_m": distance_m, "elevation_gain_m": elevation_gain_m, "days_left": days_left}

    if distance_m is None:
        return {**base, "status": "incomplete_objective", "objective": obj_out,
                "notes": [_note("incomplete_objective",
                                 "Distance de course absente de planning/active_objective.md : les cibles "
                                 "ne peuvent pas être calculées.")]}

    if days_left < 0:
        return {**base, "status": "race_past", "objective": obj_out,
                "notes": [_note("race_past",
                                 f"La course est passée ({-days_left} jour(s)) : le score de préparation "
                                 "n'a plus d'objet — voir plutôt un débrief post-course.")]}

    if distance_m < TRAIL_SHAPE_MIN_DISTANCE_M:
        return {**base, "status": "race_too_short", "objective": obj_out,
                "notes": [_note("race_too_short",
                                 f"Distance de course ({distance_m:.0f} m) sous le plancher "
                                 f"({TRAIL_SHAPE_MIN_DISTANCE_M:.0f} m, "
                                 "arc_trail_shape.TRAIL_SHAPE_MIN_DISTANCE_M) : les cibles de volume/sortie "
                                 "longue de ce score visent une préparation d'endurance de plusieurs "
                                 "semaines, pas une course courte.")]}

    notes: List[dict] = []
    if days_left / 7 > TRAIL_SHAPE_FAR_HORIZON_WEEKS:
        notes.append(_note("far_horizon",
                            f"Objectif à {days_left / 7:.0f} semaines : le bloc spécifique n'a probablement "
                            "pas commencé, ce score reflète la forme ACTUELLE, pas le pic prévu pour la "
                            "course."))

    # Activité du jour de course déjà loggée (voir la docstring du module) :
    # exclue de TOUTE composante, jamais comptée comme une séance de préparation.
    race_date_iso = objective["race_date"]
    window_start = today - timedelta(days=window_weeks * 7 - 1)

    def in_window(a: dict) -> bool:
        iso = a.get("date")
        return bool(iso) and iso != race_date_iso and window_start.isoformat() <= iso <= today.isoformat()

    # Volume hebdomadaire/plus longue sortie : course/trail UNIQUEMENT
    # (`arc_metrics.RUNNING_SPORTS`) — la randonnée/marche n'est pas un
    # stimulus comparable pour un volume ou une distance d'allure.
    running_activities = [a for a in activities if in_window(a) and a.get("sport") in M.RUNNING_SPORTS]
    # D+ max d'une séance : famille course À PIED au sens large
    # (`sport_family == "run"`, inclut la randonnée/power-hiking) — voir la
    # docstring du module, décision explicite (grimper en randonnée prépare
    # légitimement la tolérance au dénivelé).
    climb_activities = [a for a in activities if in_window(a) and M.sport_family(a.get("sport")) == "run"]

    weeks_with_data = len({_iso_week(a["date"]) for a in running_activities})
    data_confidence = "low" if weeks_with_data < TRAIL_SHAPE_MIN_WEEKS_WITH_DATA else "normal"
    if data_confidence == "low":
        notes.append(_note("low_confidence",
                            f"Seulement {weeks_with_data} semaine(s) avec au moins une séance de course à "
                            f"pied/trail sur les {window_weeks} de la fenêtre (seuil "
                            f"{TRAIL_SHAPE_MIN_WEEKS_WITH_DATA}) : confiance réduite, moyenne diluée par les "
                            "semaines sans donnée."))

    race_effort_km = _race_effort_km(distance_m, elevation_gain_m)

    # 1) Volume hebdomadaire (#35)
    total_effort_km = M.effort_km_week_total(running_activities)
    avg_weekly_effort_km = total_effort_km / window_weeks
    weekly_target = weekly_volume_target_km(race_effort_km)
    weekly_ratio = min(1.0, avg_weekly_effort_km / weekly_target) if weekly_target > 0 else None
    components = [_component("weekly_volume", weekly_target, avg_weekly_effort_km,
                              weekly_ratio, weekly_ratio is not None)]

    # 2) Plus longue sortie
    distances = [a["distance_m"] for a in running_activities if a.get("distance_m")]
    longest_m = max(distances) if distances else 0.0
    long_target = longest_run_target_m(distance_m)
    long_ratio = min(1.0, longest_m / long_target) if long_target > 0 else None
    components.append(_component("longest_run", long_target, longest_m, long_ratio, long_ratio is not None))

    # 3) D+ max d'une séance — omise sans D+ de course (route, ou D+ nul)
    if elevation_gain_m is None:
        components.append(_component("max_dplus", None, None, None, False,
                                      "D+ non renseigné pour cet objectif : cible de D+ par séance sans objet"))
    elif elevation_gain_m <= 0:
        components.append(_component("max_dplus", None, None, None, False,
                                      "D+ de course nul (route) : cible de D+ par séance sans objet"))
    else:
        dplus_values = [a.get("elevation_gain_m") or 0 for a in climb_activities]
        max_dplus = max(dplus_values) if dplus_values else 0.0
        dplus_target = min(elevation_gain_m * MAX_DPLUS_SESSION_RATIO, MAX_DPLUS_TARGET_CAP_M)
        dplus_ratio = min(1.0, max_dplus / dplus_target) if dplus_target > 0 else None
        components.append(_component("max_dplus", dplus_target, max_dplus, dplus_ratio, dplus_ratio is not None))

    # 4) Durabilité (#48) — omise si aucune sortie longue éligible sur la fenêtre.
    # `activities` non filtrée par `in_window`/course-day ici : `durability_trend`
    # applique sa propre fenêtre glissante ET son propre filtre de sport — lui
    # passer une liste déjà filtrée dupliquerait cette logique pour un résultat
    # identique (la fenêtre demandée est la même, `window_weeks`).
    durability_source = [a for a in activities if a.get("date") != race_date_iso]
    trend = M.durability_trend(durability_source, today, window_weeks)
    if trend["measured_n"] > 0:
        fade = trend["avg_gap_fade_pct"]
        durability_ratio = max(0.0, min(1.0, 1 - fade / DURABILITY_MAX_ACCEPTABLE_FADE_PCT))
        components.append(_component("durability", DURABILITY_MAX_ACCEPTABLE_FADE_PCT, fade,
                                      durability_ratio, True))
    else:
        reason = trend.get("dominant_reason") or (
            f"aucune sortie longue (> {M.LONG_RUN_MIN_DURATION_S // 60} min) sur la fenêtre"
            if trend["long_runs"] == 0 else "aucune sortie longue éligible sur la fenêtre")
        components.append(_component("durability", None, None, None, False, reason))
        notes.append(_note("durability_omitted",
                            f"Durabilité non intégrée au score : {reason} — poids redistribué sur les autres "
                            "composantes."))

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
