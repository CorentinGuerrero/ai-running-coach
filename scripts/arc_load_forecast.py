#!/usr/bin/env python3
"""Projection de charge sur le bloc planifié (#172) : forme prévue le jour de la course.

Les garde-fous (`arc_guardrails`, R1/R4) projettent l'ACWR et la monotonie sur la SEULE
semaine proposée. Ce module répond à la question centrale de l'affûtage : « avec ce plan,
dans quel état serai-je le jour J ? ». Il propage condition / fatigue / forme jour par jour
depuis l'état RÉEL d'aujourd'hui jusqu'à la date de l'objectif (`planning/active_objective.md`),
en estimant la charge de chaque séance planifiée.

Aucun second modèle de charge : tout est réutilisé.
- `arc_guardrails.projected_session_load` / `_week_loads_by_date` : charge estimée d'une
  séance planifiée (durée × RPE attendu de l'intensité × `arc_metrics.RPE_TO_TRIMP`), appariement
  séance ↔ activité réelle, durée estimée depuis la distance — EXACTEMENT ce que R1 projette ;
- `arc_metrics.daily_series` : condition (42 j) / fatigue (7 j) / forme / ACWR / monotonie ;
- `arc_guardrails.MIN_HISTORY_DAYS_FOR_PROJECTION` : même plancher d'historique que R1.

`forecast()` est PURE (aucune E/S, palier D). `load_forecast()` lit l'index dérivé (`conn`).
La projection est une ESTIMATION à partir du planifié, jamais une mesure — voir
`arc_metrics.ASSUMPTIONS["load_forecast"]`. Bibliothèque standard uniquement.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import arc_guardrails as G  # noqa: E402
import arc_metrics as M  # noqa: E402

# Statuts de sortie : chaque état honnête est dit, jamais un chiffre inventé.
STATUS_OK = "ok"
STATUS_NO_OBJECTIVE = "no_objective"
STATUS_PAST = "target_past"
STATUS_NO_PLAN = "no_plan"
STATUS_INSUFFICIENT_HISTORY = "insufficient_history"


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _parse(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    return round(value, digits) if value is not None else None


def _active_sessions(sessions: List[dict]) -> List[dict]:
    """Séances qui comptent (ni annulées/déplacées/manquées, ni repos) — même filtre que R1."""
    return [s for s in sessions if isinstance(s, dict) and not G._is_excluded(s)]


def _normalise_weeks(planned_weeks: List[dict]) -> Dict[str, List[dict]]:
    """`{lundi ISO: [séances]}` — une semaine déclarée deux fois fusionne ses séances."""
    out: Dict[str, List[dict]] = {}
    for week in planned_weeks or []:
        if not isinstance(week, dict):
            continue
        start = _parse(week.get("week_start"))
        if start is None:
            continue
        key = _monday(start).isoformat()
        out.setdefault(key, []).extend(s for s in (week.get("sessions") or []) if isinstance(s, dict))
    return out


def _summary(series: List[dict], today: date, target: date, race: Optional[date]) -> dict:
    """Points clés d'une série projetée `[today, target]` (forme à la date visée, pic de fatigue…)."""
    projected = [p for p in series if p["date"] >= today.isoformat()]
    end = projected[-1] if projected else None
    peak = max(projected, key=lambda p: p["fatigue"]) if projected else None
    acwr_points = [p for p in projected if p.get("acwr") is not None]
    acwr_peak = max(acwr_points, key=lambda p: p["acwr"]) if acwr_points else None
    race_point = next((p for p in projected if race and p["date"] == race.isoformat()), None)
    return {
        "race_day": ({"date": race_point["date"], "form": race_point["form"], "fitness": race_point["fitness"],
                      "fatigue": race_point["fatigue"], "acwr": race_point["acwr"]} if race_point else None),
        "end": ({"date": end["date"], "form": end["form"], "fitness": end["fitness"],
                 "fatigue": end["fatigue"]} if end else None),
        "peak_fatigue": ({"date": peak["date"], "week_start": _monday(date.fromisoformat(peak["date"])).isoformat(),
                          "fatigue": peak["fatigue"]} if peak else None),
        "acwr_max": ({"date": acwr_peak["date"], "value": acwr_peak["acwr"]} if acwr_peak else None),
        "planned_load_total": _round(sum(p["load"] for p in projected)),
    }


def _week_rows(series: List[dict], weeks_by_start: Dict[str, List[dict]], today: date, target: date) -> List[dict]:
    """Une ligne par semaine (lundi-dimanche) touchant `[today, target]` ; `partial` quand la
    fenêtre ne couvre pas les 7 jours (semaine en cours, semaine de course)."""
    rows = []
    monday = _monday(today)
    while monday <= target:
        days = [p for p in series if monday.isoformat() <= p["date"] <= (monday + timedelta(days=6)).isoformat()
                and today.isoformat() <= p["date"] <= target.isoformat()]
        if days:
            sessions = weeks_by_start.get(monday.isoformat())
            acwr = [p["acwr"] for p in days if p.get("acwr") is not None]
            rows.append({
                "week_start": monday.isoformat(),
                "planned": sessions is not None and bool(_active_sessions(sessions)),
                "sessions": len(_active_sessions(sessions or [])),
                "load_total": _round(sum(p["load"] for p in days)),
                "fitness_end": days[-1]["fitness"], "fatigue_end": days[-1]["fatigue"], "form_end": days[-1]["form"],
                "acwr_max": max(acwr) if acwr else None,
                "partial": len(days) < 7,
            })
        monday += timedelta(days=7)
    return rows


def forecast(real_loads: Dict[str, float], today: date, race_date: Optional[str], until: Optional[date],
             planned_weeks: List[dict], activities: Optional[List[dict]] = None,
             recent_pace_s_km: Optional[float] = None) -> dict:
    """Projection de condition/fatigue/forme sur `[today, cible]`, où cible = `until` ou la date de
    l'objectif. PURE.

    `real_loads` : charge réelle indexée par jour (< `today` seul est lu). `planned_weeks` : semaines
    (`{week_start, sessions[]}`, séances au format du contrat `week`). `activities` : activités réelles
    `{date, sport, load}` de la semaine en cours (apparient les séances d'aujourd'hui — le réel prime,
    jamais compté deux fois). Un jour sans séance planifiée compte 0 de charge (hypothèse, signalée
    par `weeks_unplanned`) ; jamais d'extrapolation de la moyenne récente."""
    race = _parse(race_date)
    target = until or race
    base = {"status": None, "today": today.isoformat(), "race_date": race.isoformat() if race else None,
            "target_date": target.isoformat() if target else None, "is_estimate": True,
            "assumptions_ref": "arc_metrics.ASSUMPTIONS[\"load_forecast\"] (/api/assumptions)"}
    if target is None:
        return {**base, "status": STATUS_NO_OBJECTIVE,
                "reason": "Aucun objectif actif (planning/active_objective.md sans date de course) et pas de "
                          "--until : rien à projeter."}
    if target < today:
        return {**base, "status": STATUS_PAST,
                "reason": f"La date visée ({target.isoformat()}) est déjà passée : rien à projeter."}

    first_real = min((date.fromisoformat(d) for d in real_loads), default=None)
    history_span = (today - first_real).days if first_real else 0
    base["history_span_days"] = history_span
    if history_span < G.MIN_HISTORY_DAYS_FOR_PROJECTION:
        return {**base, "status": STATUS_INSUFFICIENT_HISTORY,
                "reason": f"Historique réel insuffisant ({history_span} j < {G.MIN_HISTORY_DAYS_FOR_PROJECTION} j) : "
                          "la condition (moyenne exponentielle 42 j) démarre à zéro et fausserait la forme prévue — "
                          "même plancher que le garde-fou R1."}

    weeks_by_start = _normalise_weeks(planned_weeks)
    loads: Dict[str, float] = {d: v for d, v in real_loads.items() if date.fromisoformat(d) < today}
    acts_by_week: Dict[str, List[dict]] = {}
    for act in activities or []:
        day = _parse(act.get("date"))
        if day is not None:
            acts_by_week.setdefault(_monday(day).isoformat(), []).append(act)

    unresolved: List[str] = []
    estimated: List[str] = []
    planned_weeks_n, unplanned_starts = 0, []
    monday = _monday(today)
    while monday <= target:
        key = monday.isoformat()
        sessions = weeks_by_start.get(key) or []
        end_of_week = monday + timedelta(days=6)
        week_context = {"week_activities": acts_by_week.get(key, []), "recent_run_pace_s_km": recent_pace_s_km}
        day_loads = G._week_loads_by_date(week_context, sessions, monday, end_of_week, today, zero_proposed=False)
        for day_iso, load in day_loads.items():
            day = date.fromisoformat(day_iso)
            if today <= day <= target:
                loads[day_iso] = load
        if _active_sessions(sessions):
            planned_weeks_n += 1
            unresolved += G._unresolved_duration_dates(sessions, recent_pace_s_km)
            estimated += G._estimated_duration_dates(sessions, recent_pace_s_km)
        else:
            unplanned_starts.append(key)
        monday += timedelta(days=7)

    series = M.daily_series(loads, first_real, target)
    state_today = next((p for p in series if p["date"] == today.isoformat()), None)
    out = {**base, "today_state": {k: state_today[k] for k in ("fitness", "fatigue", "form", "acwr")}
           if state_today else None,
           "weeks_planned": planned_weeks_n, "weeks_unplanned": len(unplanned_starts),
           "unplanned_week_starts": unplanned_starts,
           "estimated_duration_dates": sorted(set(estimated)), "unresolved_duration_dates": sorted(set(unresolved)),
           "series": [{**p, "projected": p["date"] >= today.isoformat()} for p in series
                      if p["date"] >= (today - timedelta(days=1)).isoformat()]}
    if planned_weeks_n == 0:
        return {**out, "status": STATUS_NO_PLAN,
                "reason": "Aucune séance planifiée entre aujourd'hui et la date visée : une projection à charge "
                          "nulle ne serait pas un plan — écrire les semaines avant de projeter."}
    summary = _summary(series, today, target, race if race and today <= race <= target else None)
    out.update(summary)
    out["weeks"] = _week_rows(series, weeks_by_start, today, target)
    out["status"] = STATUS_OK
    out["partial_plan"] = bool(unplanned_starts)
    out["reason"] = None
    return out


def _compact(result: dict) -> dict:
    keys = ("race_day", "end", "peak_fatigue", "acwr_max", "planned_load_total")
    return {k: result.get(k) for k in keys}


def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return _round(b - a) if a is not None and b is not None else None


def apply_alternative(planned_weeks: List[dict], alternative_weeks: List[dict]) -> List[dict]:
    """Plan modifié : les semaines de l'alternative REMPLACENT celles du plan actuel de même lundi
    (jamais fusionnées séance à séance) ; les autres restent telles quelles ; une semaine nouvelle s'ajoute."""
    alt = _normalise_weeks(alternative_weeks)
    kept = [w for w in planned_weeks if isinstance(w, dict) and _parse(w.get("week_start"))
            and _monday(_parse(w["week_start"])).isoformat() not in alt]
    return kept + [{"week_start": k, "sessions": v} for k, v in sorted(alt.items())]


def compare(real_loads: Dict[str, float], today: date, race_date: Optional[str], until: Optional[date],
            planned_weeks: List[dict], alternative_weeks: List[dict], activities: Optional[List[dict]] = None,
            recent_pace_s_km: Optional[float] = None) -> dict:
    """Plan actuel vs plan modifié : deux projections + écarts (alternatif − actuel). PURE.
    Une projection non `ok` (historique, pas de plan…) est rendue telle quelle, sans écarts."""
    current = forecast(real_loads, today, race_date, until, planned_weeks, activities, recent_pace_s_km)
    modified_weeks = apply_alternative(planned_weeks, alternative_weeks)
    alternative = forecast(real_loads, today, race_date, until, modified_weeks, activities, recent_pace_s_km)
    replaced = sorted(set(_normalise_weeks(alternative_weeks)) & set(_normalise_weeks(planned_weeks)))
    added = sorted(set(_normalise_weeks(alternative_weeks)) - set(_normalise_weeks(planned_weeks)))
    out = {"current": current, "alternative": alternative, "replaced_weeks": replaced, "added_weeks": added,
           "deltas": None}
    if current["status"] != STATUS_OK or alternative["status"] != STATUS_OK:
        return out
    cur, alt = _compact(current), _compact(alternative)

    def pick(block, *path):
        for key in path:
            block = (block or {}).get(key) if isinstance(block, dict) else None
        return block

    deltas = {
        "race_day_form": _delta(pick(cur, "race_day", "form"), pick(alt, "race_day", "form")),
        "race_day_fitness": _delta(pick(cur, "race_day", "fitness"), pick(alt, "race_day", "fitness")),
        "race_day_fatigue": _delta(pick(cur, "race_day", "fatigue"), pick(alt, "race_day", "fatigue")),
        "end_form": _delta(pick(cur, "end", "form"), pick(alt, "end", "form")),
        "peak_fatigue": _delta(pick(cur, "peak_fatigue", "fatigue"), pick(alt, "peak_fatigue", "fatigue")),
        "acwr_max": _delta(pick(cur, "acwr_max", "value"), pick(alt, "acwr_max", "value")),
        "planned_load_total": _delta(cur["planned_load_total"], alt["planned_load_total"]),
    }
    out["deltas"] = deltas
    form_delta = deltas["race_day_form"] if deltas["race_day_form"] is not None else deltas["end_form"]
    if form_delta is not None:
        verdict = "plus fraîche" if form_delta > 0 else "moins fraîche" if form_delta < 0 else "identique"
        out["reading"] = (f"Forme prévue à la date visée : {verdict} avec le plan modifié ({form_delta:+.1f}) — "
                          "estimation à partir du planifié, pas une mesure.")
    return out


# ---------------------------------------------------------------------------
# Lecture de l'index (impure)
# ---------------------------------------------------------------------------


def _planned_weeks_from_index(conn, since: date) -> List[dict]:
    """Semaines planifiées indexées (hors `shadowed`, voir #69) dont la date est ≥ `since`."""
    rows = conn.execute(
        "SELECT week_start, date, sport, planned_duration_s, planned_distance_m, planned_elevation_m, "
        "intensity, status FROM planned_session WHERE shadowed = 0 AND date >= ? ORDER BY date",
        (since.isoformat(),)).fetchall()
    weeks: Dict[str, List[dict]] = {}
    for week_start, day, sport, duration_s, distance_m, elevation_m, intensity, status in rows:
        weeks.setdefault(week_start or _monday(date.fromisoformat(day)).isoformat(), []).append({
            "date": day, "sport": sport, "planned_duration_s": duration_s, "planned_distance_m": distance_m,
            "planned_elevation_m": elevation_m, "intensity": intensity, "status": status})
    return [{"week_start": k, "sessions": v} for k, v in sorted(weeks.items())]


def load_forecast(conn, today: date, until: Optional[date] = None,
                  alternative_weeks: Optional[List[dict]] = None) -> dict:
    """Projection depuis l'index dérivé : charge réelle, activités de la semaine en cours, semaines
    planifiées, allure récente (estimation de durée depuis une distance, comme R1) et date de l'objectif."""
    rows = conn.execute("SELECT date, load FROM activity WHERE load IS NOT NULL").fetchall()
    real_loads: Dict[str, float] = {}
    for day, load in rows:
        real_loads[day] = real_loads.get(day, 0.0) + (load or 0.0)
    monday = _monday(today)
    activities = [{"date": d, "sport": s, "load": load or 0.0} for d, s, load in conn.execute(
        "SELECT date, sport, load FROM activity WHERE date >= ?", (monday.isoformat(),)).fetchall()]
    planned = _planned_weeks_from_index(conn, monday)
    pace = G._recent_run_pace_s_km(conn, today)
    race_date = G._active_objective_race_date(conn)
    if alternative_weeks is not None:
        return compare(real_loads, today, race_date, until, planned, alternative_weeks, activities, pace)
    return forecast(real_loads, today, race_date, until, planned, activities, pace)


def alternative_weeks_from_block(block: dict) -> List[dict]:
    """Semaines d'un bloc `--compare` : fichier multi-semaines (`weeks[]`) ou semaine unique
    (`week_start` + `sessions`). `ValueError` si rien d'exploitable."""
    if isinstance(block.get("weeks"), list):
        weeks = [w for w in block["weeks"] if isinstance(w, dict) and _parse(w.get("week_start"))]
    elif _parse(block.get("week_start")):
        weeks = [block]
    else:
        weeks = []
    if not weeks:
        raise ValueError("aucune semaine exploitable (week_start + sessions, ou weeks[]).")
    return [{"week_start": w["week_start"], "sessions": w.get("sessions") or []} for w in weeks]


def render_text(result: dict) -> str:
    """Rendu texte court (CLI sans `--json`), vocabulaire générique : condition / fatigue / forme."""
    lines = []
    if "current" in result:                       # comparaison
        for label, key in (("Plan actuel", "current"), ("Plan modifié", "alternative")):
            lines.append(f"{label} :")
            lines += ["  " + ln for ln in render_text(result[key]).splitlines()]
        if result.get("deltas"):
            deltas = result["deltas"]
            lines.append("Écarts (modifié − actuel) : "
                         + ", ".join(f"{k} {v:+.1f}" for k, v in deltas.items() if v is not None))
            if result.get("reading"):
                lines.append(result["reading"])
        return "\n".join(lines)
    if result["status"] != STATUS_OK:
        return f"Projection indisponible ({result['status']}) : {result.get('reason')}"
    race_day, end = result.get("race_day"), result.get("end")
    point = race_day or end
    lines.append(f"Estimation (pas une mesure) jusqu'au {result['target_date']} — "
                 f"{result['weeks_planned']} semaine(s) planifiée(s), {result['weeks_unplanned']} non planifiée(s) "
                 "(charge nulle supposée" + (" : forme prévue optimiste)." if result["weeks_unplanned"] else ")."))
    if point:
        label = "Forme prévue le jour J" if race_day else "Forme à la date visée"
        lines.append(f"{label} ({point['date']}) : {point['form']:+.1f} "
                     f"(condition {point['fitness']:.1f}, fatigue {point['fatigue']:.1f}).")
    peak = result.get("peak_fatigue")
    if peak:
        lines.append(f"Pic de fatigue : semaine du {peak['week_start']} ({peak['fatigue']:.1f}, le {peak['date']}).")
    acwr = result.get("acwr_max")
    lines.append(f"ACWR projeté max : {acwr['value']:.2f} ({acwr['date']})." if acwr else "ACWR projeté : indisponible.")
    return "\n".join(lines)
