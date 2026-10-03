#!/usr/bin/env python3
"""Altitude (#185, épopée #170) — pénalité de course et métrique d'exposition à l'entraînement.

Fonctions **pures**, stdlib uniquement, sans accès disque : partagées par
`arc_race_pacing.py` (facteur de temps par section) et `arc_index.py altitude-exposure`
(exposition des dernières semaines). Même découpage que `arc_heat.py` (#171).

TOUS les coefficients sont des hypothèses documentées (`ASSUMPTIONS`), affichées dans le plan
(`altitude.parameters`) et réglables en CLI — jamais une vérité.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

# --- Pénalité de course -----------------------------------------------------------------------
# Seuil (m) au-dessous duquel AUCUNE pénalité n'est appliquée. Choix du projet : la source citée
# mesure déjà un effet dès 300 m, mais sur un test maximal aigu ; un ultra se court nettement
# sous le maximum et l'effet à moins de 1 500 m est négligé (approximation du projet).
ALTITUDE_THRESHOLD_M = 1500.0
# Perte de VO2max (% par 1 000 m, relative au niveau de la mer) — Wehrlin & Hallén 2006 :
# 6,3 % par 1 000 m (plage individuelle 4,6-7,5 %), linéaire de 300 à 2 800 m.
ALTITUDE_VO2MAX_LOSS_PCT_PER_1000M = 6.3
# Au-delà, extrapolation hors de la plage mesurée (2 800 m) : l'altitude est PLAFONNÉE pour le
# calcul (jamais une pénalité qui explose), et un avertissement le dit.
ALTITUDE_MEASURED_MAX_M = 2800.0
ALTITUDE_CAP_M = 4500.0
# Bornes de validation des options CLI.
ALTITUDE_LOSS_PCT_MAX = 20.0
ALTITUDE_ACCLIMATED_DAYS_MAX = 365
# Acclimatation (approximations du projet) : crédit maximal de réduction de la perte (fraction),
# atteint à `ALTITUDE_ACCLIMATION_FULL_DAYS` jours déclarés sur place ; l'acclimatation
# n'annule jamais la perte (le crédit est plafonné).
ALTITUDE_ACCLIMATION_MAX_CREDIT = 0.5
ALTITUDE_ACCLIMATION_FULL_DAYS = 14
# Exposition à l'entraînement (métrique `altitude-exposure`) : crédit plus faible, car une
# exposition intermittente (séances isolées, retour à basse altitude) protège moins qu'un séjour.
ALTITUDE_TRAINING_MAX_CREDIT = 0.25
ALTITUDE_TRAINING_FULL_HOURS = 10.0   # heures ≥ seuil sur 28 j pour le crédit maximal

# --- Métrique d'exposition --------------------------------------------------------------------
EXPOSURE_THRESHOLDS_M = (1500, 2000)
EXPOSURE_WINDOWS_DAYS = (14, 28)
# Temps minimal au-dessus d'un seuil pour qu'une séance compte comme « exposée » (évite qu'un
# col franchi 30 s ou une dérive barométrique ne fasse compter une séance).
EXPOSURE_MIN_SESSION_S = 300.0
EXPOSURE_CREDIT_WINDOW_DAYS = 28

ASSUMPTIONS: Dict[str, str] = {
    "race_penalty": (
        "Pénalité d'altitude de course (#185). Pour chaque section, altitude MOYENNE du GPX (ou "
        "corrigée par MNT quand `elevation_dem` est présent dans le plan, #176 : les altitudes du "
        "plan sont alors celles du MNT). Sous `ALTITUDE_THRESHOLD_M` (1 500 m) : aucun effet, sortie "
        "inchangée. Au-dessus : perte de VO2max = `ALTITUDE_VO2MAX_LOSS_PCT_PER_1000M` × (altitude − "
        "seuil)/1 000, et facteur de TEMPS = 1/(1 − perte × (1 − crédit d'acclimatation)). Source de "
        "la pente : Wehrlin & Hallén 2006, Eur J Appl Physiol 96:404-412, doi:10.1007/s00421-005-0081-9 "
        "(VO2max −6,3 % par 1 000 m, plage 4,6-7,5 %, linéaire de 300 à 2 800 m, 8 athlètes "
        "d'endurance, altitude simulée aiguë). **La traduction perte de VO2max -> perte de vitesse "
        "est une approximation du projet** : on suppose qu'une allure d'ultra, courue à fraction "
        "constante de la VO2max, perd la même fraction relative de vitesse. Le critère de "
        "performance de l'étude (temps jusqu'à épuisement à vitesse constante, −14,5 % par 1 000 m) "
        "n'est PAS repris : il mesure un effort proche du maximum, pas une allure d'ultra. Seuil "
        "de 1 500 m, plafond d'altitude de 4 500 m (au-delà de 2 800 m, hors plage mesurée : "
        "extrapolation, signalée) : choix du projet. Facteur identique pour les trois scénarios "
        "(l'ordre prudent >= réaliste >= ambitieux est donc conservé), composé multiplicativement "
        "avec chaleur et nuit, section par section, avant la nuit. Limites : effet individuel très "
        "variable (4,6-7,5 % mesuré), pas de modèle du mal aigu des montagnes, de l'hydratation ni "
        "de la descente (la montée en altitude et le séjour comptent autant que l'altitude)."),
    "acclimation": (
        "Acclimatation (approximations du projet, aucune valeur publiée reprise telle quelle) : "
        "crédit de réduction de la perte = min(`ALTITUDE_ACCLIMATION_MAX_CREDIT` (0,5), 0,5 × jours "
        "déclarés sur place/`ALTITUDE_ACCLIMATION_FULL_DAYS` (14)) — `--altitude-acclimated-days N` ; "
        "plus, si l'index contient des séances avec altitude, un crédit d'exposition à l'entraînement "
        "= `ALTITUDE_TRAINING_MAX_CREDIT` (0,25) × min(1, heures ≥ 1 500 m sur 28 j/10). Les deux "
        "crédits s'ajoutent, plafonnés à 0,5 : l'acclimatation n'annule jamais la pénalité. Un pari "
        "optimiste sur une acclimatation supposée est plus risqué qu'un plan trop prudent : sans "
        "déclaration ni exposition mesurée, le crédit est NUL (athlète non acclimaté)."),
    "exposure": (
        "Exposition à l'altitude à l'entraînement (#185, `arc_index.py altitude-exposure`, sur le "
        "modèle de `heat-acclimation`). Fenêtres glissantes de 14 et 28 jours (`--days N` pour une "
        "seule) se terminant à `--today`. Source : les ÉCHANTILLONS FIT ingérés (`activity_sample."
        "altitude_m`) ; le temps au-dessus de chaque seuil (1 500 m, 2 000 m) est la somme des "
        "`covered_s` (1 s si absent). Une séance compte au seuil si elle y passe au moins "
        "`EXPOSURE_MIN_SESSION_S` (5 min). Les résumés d'activité du contrat ne portent aucune "
        "altitude absolue (seulement le dénivelé) : une séance SANS échantillon ou sans altitude est "
        "comptée à part (`sessions_without_altitude`), jamais comme exposition nulle. Altitude "
        "barométrique ou GPS bruitée (quelques dizaines de mètres) : l'exposition près d'un seuil est "
        "approximative. Ce n'est pas un modèle d'acclimatation physiologique : un indicateur d'exposition."),
}


def altitude_credit(acclimated_days: Optional[int], training_hours_ge_threshold: Optional[float]) -> Dict[str, float]:
    """Crédit d'acclimatation (fraction de la perte annulée) : déclaré + entraînement, plafonné."""
    declared = 0.0
    if acclimated_days and acclimated_days > 0:
        declared = ALTITUDE_ACCLIMATION_MAX_CREDIT * min(1.0, acclimated_days / ALTITUDE_ACCLIMATION_FULL_DAYS)
    training = 0.0
    if training_hours_ge_threshold and training_hours_ge_threshold > 0:
        training = ALTITUDE_TRAINING_MAX_CREDIT * min(1.0, training_hours_ge_threshold / ALTITUDE_TRAINING_FULL_HOURS)
    total = min(ALTITUDE_ACCLIMATION_MAX_CREDIT, declared + training)
    return {"declared": round(declared, 4), "training": round(training, 4), "total": round(total, 4)}


def altitude_time_factor(altitude_m: Optional[float], *, credit: float = 0.0,
                         threshold_m: float = ALTITUDE_THRESHOLD_M,
                         loss_pct_per_1000m: float = ALTITUDE_VO2MAX_LOSS_PCT_PER_1000M) -> float:
    """Facteur multiplicatif de TEMPS (>= 1.0) pour une altitude moyenne de section. 1.0 si
    l'altitude est inconnue ou <= au seuil. Approximation du projet (voir `ASSUMPTIONS`)."""
    if altitude_m is None or altitude_m <= threshold_m:
        return 1.0
    alt = min(altitude_m, ALTITUDE_CAP_M)
    loss = (loss_pct_per_1000m / 100.0) * (alt - threshold_m) / 1000.0 * (1.0 - credit)
    loss = max(0.0, min(loss, 0.5))
    return 1.0 / (1.0 - loss)


def exposure_report(rows: Sequence[dict], today, windows: Sequence[int] = EXPOSURE_WINDOWS_DAYS,
                    thresholds: Sequence[int] = EXPOSURE_THRESHOLDS_M) -> dict:
    """Agrège des lignes par séance `{date, max_altitude_m, altitude_s, above_s: {seuil: s}}`
    (`altitude_s` None = aucun échantillon d'altitude) en rapport par fenêtre. Pure."""
    from datetime import date as _date, timedelta
    out_windows: Dict[str, dict] = {}
    for w in windows:
        start = today - timedelta(days=w - 1)
        sel = [r for r in rows if start <= _date.fromisoformat(r["date"]) <= today]
        with_alt = [r for r in sel if r.get("altitude_s")]
        entry = {
            "window_days": w, "sessions": len(sel), "sessions_with_altitude": len(with_alt),
            "sessions_without_altitude": len(sel) - len(with_alt),
            "max_altitude_m": (round(max(r["max_altitude_m"] for r in with_alt)) if with_alt else None),
            "thresholds": {},
        }
        for thr in thresholds:
            secs = [(r.get("above_s") or {}).get(thr, 0.0) or 0.0 for r in with_alt]
            entry["thresholds"][str(thr)] = {
                "threshold_m": thr,
                "sessions": sum(1 for s in secs if s >= EXPOSURE_MIN_SESSION_S),
                "duration_s": round(sum(secs)),
            }
        out_windows[str(w)] = entry
    longest = out_windows[str(max(windows))] if windows else None
    if not rows:
        status, note = "no_activity", "aucune séance indexée"
    elif longest and not longest["sessions"]:
        status, note = "no_activity", "aucune séance dans la fenêtre"
    elif longest and not longest["sessions_with_altitude"]:
        status, note = "no_altitude", ("séances présentes mais aucune avec altitude : échantillons FIT absents "
                                        "ou capteur d'altitude muet (voir `skills/fit-download`)")
    else:
        top = longest["thresholds"][str(thresholds[0])]
        status = "exposed" if top["sessions"] else "none"
        note = ("exposition mesurée" if status == "exposed"
                else f"aucune séance ≥ {thresholds[0]} m sur {longest['window_days']} jours")
    return {"status": status, "note": note, "windows": out_windows,
            "thresholds_m": list(thresholds), "min_session_s": EXPOSURE_MIN_SESSION_S,
            "assumption": ASSUMPTIONS["exposure"]}


def training_hours_ge(report: Optional[dict], threshold_m: int = 1500) -> Optional[float]:
    """Heures ≥ `threshold_m` sur la fenêtre de crédit (28 j), ou `None` si inconnu/aucune donnée."""
    if not report or report.get("status") in (None, "no_activity", "no_altitude"):
        return None
    w = (report.get("windows") or {}).get(str(EXPOSURE_CREDIT_WINDOW_DAYS))
    if not w:
        return None
    t = (w.get("thresholds") or {}).get(str(threshold_m))
    return None if not t else t["duration_s"] / 3600.0
