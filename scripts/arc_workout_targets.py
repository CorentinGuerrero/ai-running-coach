#!/usr/bin/env python3
"""Cibles personnelles d'une séance structurée — zones FC, allure GAP, D+ de
côte (#60, épopée #23).

## Pourquoi (vs pousser une séance « à l'aveugle »)

`skills/garmin-workout-scheduling` sait déjà construire le DTO Garmin d'une
séance ; ce module lui fournit les CIBLES à y mettre — celles de l'ATHLÈTE,
jamais des bornes génériques inventées :

- **Zones FC** (#43, `arc_metrics.hr_zone_resolution`) : bornes bpm par
  méthode réellement calculable pour le profil (LTHR -> Karvonen -> %FCmax),
  mappées depuis l'INTENSITÉ planifiée de la séance (`arc_contract.INTENSITY`).
- **Allure GAP plate** (#44/#58, `arc_slope_model.predict_speed`) : référence
  plate personnelle (ou générique, provenance explicite) pour un pas de plat
  en endurance/récupération.
- **Répétitions de côte** : durée + D+ ATTENDU (jamais mesuré à l'avance,
  toujours une PRÉVISION) à partir de la vitesse personnelle prédite à la
  pente demandée × la durée du répétitif.

Aucune cible n'est jamais inventée : quand le profil ou le modèle ne permet
pas de la calculer, la sortie porte `reason`/`reason_code` et le champ cible
reste `None` — jamais une valeur par défaut générique présentée comme
personnelle (même discipline que #43/#58/#59).

## Mapping intensité -> zone FC

`INTENSITY_TO_ZONE` : `recovery` -> Z1, `endurance` -> Z2, `tempo` -> Z3,
`threshold` -> Z4, `vo2max` -> Z5 — cohérent avec le nombre de zones rendues
par `arc_metrics.hr_zone_bounds` (6 bornes pour 5 zones, quelle que soit la
méthode). `race`, `rest`, `strength` n'ont PAS de mapping zone FC ici (une
course a son propre plan d'allure, #59 ; le repos et le renforcement n'ont pas
de zone FC de course à pied pertinente) : `reason_code="unmapped_intensity"`.

## Allure plate — pourquoi seulement recovery/endurance

`arc_slope_model` n'ajuste aujourd'hui qu'une courbe pente -> allure pour la
bande `"endurance"` (voir `arc_slope_model.BANDS`) : c'est la SEULE référence
de vitesse à effort constant que le projet peut calculer avec confiance pour
CET athlète. Un pas de tempo/seuil/VO2max demanderait de mettre cette
référence à l'échelle d'un effort plus dur — le projet n'a PAS de modèle
personnel validé pour cette mise à l'échelle sur une séance d'ENTRAÎNEMENT
(à la différence de #59, qui la dérive d'un OBJECTIF DE COURSE avec une
référence dure choisie et un exposant de Riegel/VDOT — un calcul spécifique à
une distance de course, pas transposable tel quel à « le pas de 6 min à
allure seuil d'une séance de fractionné »). Plutôt que d'inventer un facteur
d'échelle non validé, ce module ne rend PAS de cible d'allure plate pour
`tempo`/`threshold`/`vo2max`/`race`/`rest`/`strength`
(`reason_code="no_personal_pace_scaling_for_intensity"`) : ces séances-là se
pilotent par zone FC ou par ressenti, jamais par une allure GAP inventée.
Documenté honnêtement comme une limite du projet, pas un oubli — à lever si
une future story ajuste un modèle personnel effort par effort.

## Répétitions de côte — méthode

`hill_repeat_targets(structure, bins)` : `structure` = `{"reps", "rep_duration_s",
"grade_pct", "recovery_s"?}`. Pour chaque répétition : vitesse prédite à cette
pente (`arc_slope_model.predict_speed(grade_pct/100, bins)`, bande fournie par
l'appelant — `"endurance"` par défaut, seule bande dont la provenance
personnelle est understood/documentée par #58) x durée du répétitif = distance
parcourue ; D+ attendu = distance x pente (seulement si `grade_pct > 0` — un
« répétitif de côte » suppose une montée ; une pente nulle ou négative rend
`reason_code="grade_not_positive"`, jamais un D+ négatif présenté comme un D+
de montée). Le D+ est une PRÉVISION à effort constant (personnel ou générique
selon la pente, voir `arc_slope_model.ASSUMPTIONS['fallback']`), pas une
promesse — les paniers de forte pente sont souvent en repli générique faute
d'historique suffisant : `source`/`reason_code` par répétitif le disent
explicitement.

## Unités du DTO Garmin (skills/garmin-workout-scheduling/SKILL.md)

- **FC** (`targetType: heart.rate.zone`, bornes personnalisées) :
  `targetValueOne`/`targetValueTwo` en **bpm**, entiers (arrondis) — la borne
  basse d'abord (`targetValueOne`), la borne haute ensuite
  (`targetValueTwo`), même convention que l'exemple du skill.
- **Allure** (`targetType: pace.zone`) : `targetValueOne`/`targetValueTwo` en
  **mètres par seconde**, PAS en s/km — confirmé sur le schéma Garmin
  reverse-engineered utilisé par `python-garminconnect` (PR #440, classe
  `PaceTarget`, « upper and lower limits in m/s » ; `targetValueOne` =
  `lower_limit`, c-à-d la vitesse la plus FAIBLE = l'allure la plus LENTE,
  `targetValueTwo` = `upper_limit` = la vitesse la plus ÉLEVÉE = l'allure la
  plus RAPIDE — jamais l'inverse). Ce module calcule tout en m/s en interne
  (comme `arc_gap`/`arc_slope_model`) : AUCUNE conversion s/km -> m/s n'est
  donc nécessaire côté DTO, seul le sens des bornes (lente -> rapide) compte.
  `pace_s_km_to_speed_ms`/`speed_ms_to_pace_s_km` ci-dessous restent exposées
  pour l'affichage humain (jamais pour le DTO).
- **Durée** (`endCondition: time`) : `endConditionValue` en **secondes**,
  jamais en minutes — `hill_repeat_targets` prend déjà `rep_duration_s` en
  secondes en entrée, aucune conversion à faire par l'appelant.
- **D+ attendu** : mètres — Garmin n'a PAS de champ DTO pour un dénivelé
  cible sur un pas d'entraînement (seule `endCondition`/`targetType`
  existent) : c'est une information de PROVENANCE/PRÉVISION à afficher dans
  la description du pas ou au coureur, jamais un champ du DTO.

Stdlib uniquement (CONTRIBUTING.md).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arc_metrics as M  # noqa: E402
import arc_slope_model as SL  # noqa: E402

# Intensité planifiée (`arc_contract.INTENSITY`) -> numéro de zone FC (1..5).
# `race`/`rest`/`strength` volontairement ABSENTS (voir docstring du module).
INTENSITY_TO_ZONE: Dict[str, int] = {
    "recovery": 1,
    "endurance": 2,
    "tempo": 3,
    "threshold": 4,
    "vo2max": 5,
}

# Intensités pour lesquelles une cible d'allure PLATE personnelle a un sens
# (voir docstring « Allure plate — pourquoi seulement recovery/endurance »).
FLAT_PACE_INTENSITIES = ("recovery", "endurance")

# Bande du modèle pente -> allure utilisée par défaut pour tout ce module —
# seule bande dont #58 documente la provenance personnelle/générique par
# panier (voir `arc_slope_model.BANDS`).
DEFAULT_BAND = "endurance"

# Tolérance appliquée de part et d'autre de la référence plate personnelle
# pour construire une PLAGE d'allure (le DTO Garmin `pace.zone` attend deux
# bornes, jamais une valeur unique) — choix de projet documenté (pas une
# mesure), volontairement modeste : la référence plate elle-même est déjà une
# médiane pondérée par le temps (#58), l'élargir de trop diluerait son
# utilité comme cible.
FLAT_PACE_TOLERANCE_PCT = 0.05


def pace_s_km_to_speed_ms(pace_s_km: Optional[float]) -> Optional[float]:
    """Allure (s/km) -> vitesse (m/s). `None`/valeur non positive -> `None`,
    jamais une division par zéro ni une vitesse infinie."""
    if not pace_s_km or pace_s_km <= 0:
        return None
    return 1000.0 / pace_s_km


def speed_ms_to_pace_s_km(speed_ms: Optional[float]) -> Optional[float]:
    """Vitesse (m/s) -> allure (s/km). `None`/valeur non positive -> `None`."""
    if not speed_ms or speed_ms <= 0:
        return None
    return 1000.0 / speed_ms


def hr_target_for_intensity(intensity: Optional[str], athlete: dict,
                             hr_zones_method: Optional[str] = None) -> dict:
    """Cible FC (bpm) pour une intensité planifiée, à partir des zones DE CET
    ATHLÈTE (`arc_metrics.hr_zone_resolution`, #43).

    Rend TOUJOURS `{"bounds_bpm": [low, high] | None, "zone": int | None,
    "method": str | None, "reason": str | None, "reason_code": str | None}` —
    jamais d'exception. `bounds_bpm` est `None` (jamais des bornes inventées)
    dès que l'intensité n'a pas de mapping zone FC, ou que le profil ne permet
    de calculer aucune méthode de zones."""
    if intensity not in INTENSITY_TO_ZONE:
        known = ", ".join(INTENSITY_TO_ZONE)
        return {
            "bounds_bpm": None, "zone": None, "method": None,
            "reason": f"intensité « {intensity} » sans zone FC de course à pied associée "
                      f"(mapping défini pour : {known})",
            "reason_code": "unmapped_intensity",
        }
    resolution = M.hr_zone_resolution(athlete, hr_zones_method)
    if resolution["bounds_bpm"] is None:
        return {
            "bounds_bpm": None, "zone": INTENSITY_TO_ZONE[intensity], "method": resolution["method"],
            "reason": resolution["reason"], "reason_code": "no_zone_data",
        }
    zone = INTENSITY_TO_ZONE[intensity]
    bounds = resolution["bounds_bpm"]
    low, high = bounds[zone - 1], bounds[zone]
    return {
        "bounds_bpm": [round(low), round(high)], "zone": zone, "method": resolution["method"],
        "reason": None, "reason_code": None,
    }


def flat_pace_target_for_intensity(intensity: Optional[str], bins: Sequence[dict],
                                    *, tolerance_pct: float = FLAT_PACE_TOLERANCE_PCT) -> dict:
    """Cible d'allure GAP PLATE (m/s, bornes basse/haute) pour un pas de route
    d'une séance d'intensité `intensity` — voir docstring du module pour la
    restriction aux intensités `recovery`/`endurance`.

    Rend TOUJOURS `{"speed_low_ms", "speed_high_ms", "pace_low_s_km",
    "pace_high_s_km", "source", "reason", "reason_code"}` — jamais
    d'exception ; les 4 premières clés valent `None` sans cible calculable."""
    empty = {"speed_low_ms": None, "speed_high_ms": None, "pace_low_s_km": None,
              "pace_high_s_km": None, "source": None}
    if intensity not in FLAT_PACE_INTENSITIES:
        known = ", ".join(FLAT_PACE_INTENSITIES)
        return {**empty,
                "reason": f"pas de mise à l'échelle personnelle validée d'une allure plate pour l'intensité "
                          f"« {intensity} » (seules {known} ont une référence plate directement exploitable, "
                          "voir docstring du module) : piloter ce pas par zone FC plutôt que par allure",
                "reason_code": "no_personal_pace_scaling_for_intensity"}
    prediction = SL.predict_speed(0.0, bins)
    if prediction["speed_ms"] is None:
        return {**empty, "reason": prediction["reason"], "reason_code": prediction["reason_code"] or "no_model"}
    base = prediction["speed_ms"]
    low = base * (1.0 - tolerance_pct)
    high = base * (1.0 + tolerance_pct)
    return {
        "speed_low_ms": low, "speed_high_ms": high,
        "pace_low_s_km": speed_ms_to_pace_s_km(high),   # allure la plus RAPIDE = vitesse la plus haute
        "pace_high_s_km": speed_ms_to_pace_s_km(low),   # allure la plus LENTE = vitesse la plus basse
        "source": prediction["source"], "reason": prediction["reason"], "reason_code": prediction["reason_code"],
    }


def _validate_hill_structure(structure: dict) -> Optional[str]:
    reps = structure.get("reps")
    rep_duration_s = structure.get("rep_duration_s")
    grade_pct = structure.get("grade_pct")
    if not isinstance(reps, int) or reps < 1:
        return "« reps » attendu : entier >= 1"
    if not isinstance(rep_duration_s, (int, float)) or rep_duration_s <= 0:
        return "« rep_duration_s » attendu : nombre > 0 (secondes)"
    if not isinstance(grade_pct, (int, float)):
        return "« grade_pct » attendu : nombre (pourcentage, ex. 8 pour 8 %)"
    return None


def hill_repeat_targets(structure: dict, bins: Sequence[dict], *, band: str = DEFAULT_BAND) -> dict:
    """Cibles durée/D+ d'un répétitif de côte — voir docstring du module.

    `structure` : `{"reps": int, "rep_duration_s": num, "grade_pct": num,
    "recovery_s": num?}`. Rend TOUJOURS un dict avec `reps`, `rep_duration_s`,
    `grade_pct`, `recovery_s`, `per_rep` (`speed_ms`, `distance_m`,
    `elevation_gain_m`, `source`, `reason`, `reason_code`),
    `total_elevation_gain_m`, `total_work_duration_s` — jamais d'exception ;
    `per_rep`/`total_elevation_gain_m` restent `None` quand le D+ n'est pas
    calculable (raison explicite dans `per_rep`)."""
    error = _validate_hill_structure(structure)
    reps = structure.get("reps")
    rep_duration_s = structure.get("rep_duration_s")
    grade_pct = structure.get("grade_pct")
    recovery_s = structure.get("recovery_s")
    base = {
        "reps": reps, "rep_duration_s": rep_duration_s, "grade_pct": grade_pct, "recovery_s": recovery_s,
        "total_work_duration_s": (reps * rep_duration_s) if isinstance(reps, int) and
                                   isinstance(rep_duration_s, (int, float)) else None,
    }
    if error:
        return {**base, "per_rep": None, "total_elevation_gain_m": None,
                "reason": error, "reason_code": "invalid_structure"}
    if grade_pct <= 0:
        return {**base, "per_rep": None, "total_elevation_gain_m": None,
                "reason": f"pente non positive ({grade_pct:g} %) : un répétitif de côte suppose une pente "
                          "montante, D+ non calculé (jamais un D+ négatif présenté comme un dénivelé de montée)",
                "reason_code": "grade_not_positive"}
    grade = grade_pct / 100.0
    prediction = SL.predict_speed(grade, bins)
    if prediction["speed_ms"] is None:
        return {**base, "per_rep": {
                    "speed_ms": None, "distance_m": None, "elevation_gain_m": None, "source": None,
                    "reason": prediction["reason"], "reason_code": prediction["reason_code"] or "no_model"},
                "total_elevation_gain_m": None,
                "reason": prediction["reason"], "reason_code": prediction["reason_code"] or "no_model"}
    speed = prediction["speed_ms"]
    distance_m = speed * rep_duration_s
    elevation_gain_m = distance_m * grade
    per_rep = {
        "speed_ms": speed, "distance_m": distance_m, "elevation_gain_m": elevation_gain_m,
        "source": prediction["source"], "reason": prediction["reason"], "reason_code": prediction["reason_code"],
    }
    return {**base, "per_rep": per_rep, "total_elevation_gain_m": elevation_gain_m * reps,
            "reason": None, "reason_code": None, "band": band}


def build_session_targets(session: dict, *, athlete: dict, bins: Sequence[dict],
                           hr_zones_method: Optional[str] = None, band: str = DEFAULT_BAND) -> dict:
    """Point d'entrée unique : `session` (voir `arc_contract.SUBSCHEMA["session"]`,
    plus une clé `structure` optionnelle, HORS contrat `arc`, pour un répétitif
    de côte — voir CLI `targets` et `parse_structure_text`).

    Rend `{"intensity", "sport", "hr_target", "pace_target", "hill_repeats"}` —
    `pace_target` est `None` quand `structure` est fournie (une séance de
    répétitifs de côte n'a pas de pas plat à cibler par ce module) ;
    `hill_repeats` est `None` sinon."""
    intensity = session.get("intensity")
    structure = session.get("structure")
    hr_target = hr_target_for_intensity(intensity, athlete, hr_zones_method)
    if structure:
        return {
            "intensity": intensity, "sport": session.get("sport"),
            "hr_target": hr_target, "pace_target": None,
            "hill_repeats": hill_repeat_targets(structure, bins, band=band),
        }
    return {
        "intensity": intensity, "sport": session.get("sport"),
        "hr_target": hr_target, "pace_target": flat_pace_target_for_intensity(intensity, bins),
        "hill_repeats": None,
    }


# ---------------------------------------------------------------------------
# Analyseur best-effort d'une structure en texte libre — ex. « 6×3 min côte 8 % »
# ---------------------------------------------------------------------------

import re  # noqa: E402

# `6x3min côte 8%`, `6 × 3 min à 8%`, `6x3 min de côte à 8,5 %`… — reps,
# durée du répétitif (minutes), pente (%). Volontairement ÉTROIT : un texte
# qui ne correspond pas exactement à ce gabarit rend `None` plutôt qu'un
# résultat partiel deviné (jamais de structure inventée depuis une formulation
# ambiguë) — l'appelant doit alors fournir `structure` explicitement (JSON).
_HILL_STRUCTURE_RE = re.compile(
    r"(?P<reps>\d+)\s*[x×]\s*(?P<minutes>\d+(?:[.,]\d+)?)\s*min(?:ute)?s?"
    r".{0,20}?c[oô]te.{0,10}?(?P<grade>\d+(?:[.,]\d+)?)\s*%",
    re.IGNORECASE,
)


def parse_structure_text(text: Optional[str]) -> Optional[dict]:
    """Best-effort : `"6×3 min côte 8 %"` -> `{"reps": 6, "rep_duration_s": 180,
    "grade_pct": 8.0}` (jamais de `recovery_s`, pas dans ce gabarit). `None` si
    `text` ne correspond pas — jamais une structure devinée partiellement."""
    if not text:
        return None
    m = _HILL_STRUCTURE_RE.search(text)
    if not m:
        return None
    reps = int(m.group("reps"))
    minutes = float(m.group("minutes").replace(",", "."))
    grade = float(m.group("grade").replace(",", "."))
    return {"reps": reps, "rep_duration_s": minutes * 60.0, "grade_pct": grade}


# ---------------------------------------------------------------------------
# Validation minimale d'un pas de DTO Garmin (skills/garmin-workout-scheduling)
# ---------------------------------------------------------------------------

_STEP_TYPE_IDS = {1: "warmup", 2: "cooldown", 3: "interval", 4: "recovery", 5: "rest", 6: "repeat"}
_END_CONDITION_IDS = {1: "lap.button", 2: "time", 3: "distance", 7: "iterations", 10: "reps"}
_TARGET_TYPE_IDS = {1: "no.target", 4: "heart.rate.zone", 6: "pace.zone"}


def validate_workout_step_dto(step: dict) -> List[str]:
    """Valide un pas `ExecutableStepDTO` contre le schéma documenté par
    `skills/garmin-workout-scheduling/SKILL.md` — vérification de FORME
    minimale (clés/ids/cohérence), jamais un appel réseau. Rend une liste
    d'erreurs (vide = valide)."""
    errors: List[str] = []
    if step.get("type") != "ExecutableStepDTO":
        errors.append(f"type attendu 'ExecutableStepDTO', reçu {step.get('type')!r}")
    if not isinstance(step.get("stepOrder"), int) or step["stepOrder"] < 1:
        errors.append("stepOrder attendu : entier >= 1")
    step_type = step.get("stepType") or {}
    if step_type.get("stepTypeId") not in _STEP_TYPE_IDS:
        errors.append(f"stepType.stepTypeId inconnu : {step_type.get('stepTypeId')!r}")
    elif step_type.get("stepTypeKey") != _STEP_TYPE_IDS[step_type["stepTypeId"]]:
        errors.append(f"stepType.stepTypeKey incohérent avec stepTypeId {step_type['stepTypeId']}")
    end_cond = step.get("endCondition") or {}
    cond_id = end_cond.get("conditionTypeId")
    if cond_id not in _END_CONDITION_IDS:
        errors.append(f"endCondition.conditionTypeId inconnu : {cond_id!r}")
    elif end_cond.get("conditionTypeKey") != _END_CONDITION_IDS[cond_id]:
        errors.append(f"endCondition.conditionTypeKey incohérent avec conditionTypeId {cond_id}")
    if cond_id != 1 and "endConditionValue" not in step:
        errors.append("endConditionValue manquant (obligatoire sauf endCondition lap.button)")
    target_type = step.get("targetType") or {}
    target_id = target_type.get("workoutTargetTypeId")
    if target_id not in _TARGET_TYPE_IDS:
        errors.append(f"targetType.workoutTargetTypeId inconnu : {target_id!r}")
    elif target_type.get("workoutTargetTypeKey") != _TARGET_TYPE_IDS[target_id]:
        errors.append(f"targetType.workoutTargetTypeKey incohérent avec workoutTargetTypeId {target_id}")
    if target_id == 4:  # heart.rate.zone
        has_zone = "zoneNumber" in step
        has_range = "targetValueOne" in step and "targetValueTwo" in step
        if has_zone == has_range:
            errors.append("cible heart.rate.zone : soit zoneNumber SEUL, soit targetValueOne+targetValueTwo, "
                           "jamais les deux ni aucun")
    elif target_id == 6:  # pace.zone
        if "targetValueOne" not in step or "targetValueTwo" not in step:
            errors.append("cible pace.zone : targetValueOne ET targetValueTwo (m/s) attendus")
        elif step["targetValueOne"] > step["targetValueTwo"]:
            errors.append("pace.zone : targetValueOne (vitesse basse = allure lente) doit être <= targetValueTwo "
                           "(vitesse haute = allure rapide)")
    return errors


def dto_hr_step(step_order: int, *, description: str, duration_s: float, bounds_bpm: Sequence[float],
                 step_type_id: int = 3) -> dict:
    """Construit un `ExecutableStepDTO` de durée `duration_s` (secondes) ciblant
    une plage FC personnalisée `bounds_bpm` (`[low, high]`, bpm, arrondis à
    l'entier) — voir docstring du module pour la provenance des unités."""
    step_type_key = _STEP_TYPE_IDS[step_type_id]
    low, high = bounds_bpm
    return {
        "type": "ExecutableStepDTO", "stepOrder": step_order,
        "stepType": {"stepTypeId": step_type_id, "stepTypeKey": step_type_key},
        "description": description,
        "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
        "endConditionValue": round(duration_s),
        "targetType": {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone"},
        "targetValueOne": round(low), "targetValueTwo": round(high),
    }


def dto_pace_step(step_order: int, *, description: str, duration_s: float, speed_low_ms: float,
                   speed_high_ms: float, step_type_id: int = 3) -> dict:
    """Construit un `ExecutableStepDTO` de durée `duration_s` (secondes) ciblant
    une plage d'allure `[speed_low_ms, speed_high_ms]` (m/s — PAS de conversion
    depuis s/km, voir docstring du module)."""
    step_type_key = _STEP_TYPE_IDS[step_type_id]
    return {
        "type": "ExecutableStepDTO", "stepOrder": step_order,
        "stepType": {"stepTypeId": step_type_id, "stepTypeKey": step_type_key},
        "description": description,
        "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
        "endConditionValue": round(duration_s),
        "targetType": {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone"},
        "targetValueOne": speed_low_ms, "targetValueTwo": speed_high_ms,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_session_arg(value: str, workspace: Path) -> dict:
    """`--session` : soit un JSON inline (`{"intensity": "endurance", ...}`),
    soit `chemin/vers/Semaine.md#AAAA-MM-JJ` (une session du bloc ```arc
    `week.sessions[]` de ce fichier, sélectionnée par sa `date`)."""
    import json
    if "#" not in value:
        return json.loads(value)
    file_part, _, date_part = value.rpartition("#")
    path = Path(file_part)
    if not path.is_absolute():
        path = workspace / path
    text = path.read_text(encoding="utf-8")
    start = text.find("```arc")
    if start == -1:
        raise ValueError(f"{path} : aucun bloc ```arc trouvé")
    start = text.find("\n", start) + 1
    end = text.find("```", start)
    block = json.loads(text[start:end])
    for sess in block.get("sessions", []):
        if sess.get("date") == date_part:
            return sess
    raise ValueError(f"{path} : aucune séance datée {date_part} dans sessions[]")


def build_arg_parser():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=("targets",))
    ap.add_argument("--session", required=True,
                     help="séance en JSON inline, ou chemin/Semaine.md#AAAA-MM-JJ")
    ap.add_argument("--workspace", default=".", help="racine du workspace (défaut : répertoire courant)")
    ap.add_argument("--db", help="chemin de l'index SQLite (défaut : <workspace>/.arc/coach.db)")
    ap.add_argument("--memory", action="store_true", help="index en mémoire (tests)")
    ap.add_argument("--band", choices=SL.BANDS, default=DEFAULT_BAND,
                     help="bande du modèle pente -> allure (défaut : endurance)")
    ap.add_argument("--today", metavar="AAAA-MM-JJ")
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    import json
    args = build_arg_parser().parse_args(argv)
    workspace = Path(args.workspace)
    try:
        session = _load_session_arg(args.session, workspace)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 1

    import arc_index as IDX  # noqa: E402 (import tardif, comme arc_race_pacing)
    conn = IDX.open_db(workspace, args.db, args.memory)
    IDX.index_workspace(conn, workspace, args.today)
    conf = IDX.settings(IDX.load_config(workspace))
    athlete_row = conn.execute("SELECT * FROM athlete LIMIT 1").fetchone()
    athlete = dict(athlete_row) if athlete_row else {}
    report = IDX.slope_model_report(conn, args.band)
    bins = report.get("bins") or []

    result = build_session_targets(session, athlete=athlete, bins=bins,
                                    hr_zones_method=conf.get("hr_zones"), band=args.band)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
