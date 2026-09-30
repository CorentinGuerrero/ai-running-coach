#!/usr/bin/env python3
"""Synthèse « Foulée » (#151, épopée #131) : dynamique de course mesurée + indices d'inspection.

Fonctions **pures** (aucun SQLite, aucun accès disque) : la lecture en base est faite par
`scripts/arc_index.py::gait_summary`, qui rassemble deux familles de données et les passe ici.

1. **Dynamique de course mesurée** (montre Garmin, échantillons FIT — `arc_samples.DYNAMICS_KEYS`) :
   temps de contact au sol, balance du temps de contact, oscillation verticale, ratio vertical,
   longueur de pas, cadence. Une valeur par séance de COURSE (route + trail ; marche, randonnée,
   vélo exclus), puis une tendance par grandeur.
2. **Indices d'inspection photo** (`gear/*_inspection.md`, #135) : indice d'attaque (`gait_hints`),
   asymétrie d'usure — des INDICES posés d'après des photos de semelle, jamais des mesures.

La synthèse **n'est jamais un diagnostic** et **ne modifie ni la charge ni le plan** : elle dit ce
qui est mesuré, ce qui est deviné, avec quelle confiance, et où les deux se contredisent (la mesure
l'emporte alors, dit explicitement).

Bibliothèque standard uniquement (CONTRIBUTING.md).
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Grandeurs suivies, dans l'ordre d'affichage. `cadence_spm` = pas/min (deux pieds) — voir
# ASSUMPTIONS["cadence"].
METRICS = ("ground_contact_s", "stance_balance_pct", "vertical_oscillation_m",
           "vertical_ratio_pct", "step_length_m", "cadence_spm")

# Clés optionnelles du bloc `arc` d'une séance (contrat) : repli quand les échantillons FIT de la
# séance n'ont pas été ingérés. Les échantillons, eux, priment toujours.
ARC_KEYS = {
    "ground_contact_s": "avg_ground_contact_s",
    "stance_balance_pct": "avg_stance_balance_pct",
    "vertical_oscillation_m": "avg_vertical_oscillation_m",
    "vertical_ratio_pct": "avg_vertical_ratio_pct",
    "step_length_m": "avg_step_length_m",
    "cadence_spm": "avg_cadence_spm",
}

# Même fenêtre plausible que `arc_samples.DYNAMICS_PLAUSIBLE` pour les valeurs venues du bloc `arc`
# (saisies à la main ou copiées par un agent) ; la cadence est traitée à part (piège documenté).
PLAUSIBLE = {
    "ground_contact_s": (0.05, 1.0),
    "stance_balance_pct": (30.0, 70.0),
    "vertical_oscillation_m": (0.01, 0.30),
    "vertical_ratio_pct": (1.0, 30.0),
    "step_length_m": (0.2, 3.0),
    "cadence_spm": (120.0, 240.0),
}

# Bande « symétrique » de la balance du temps de contact : 50 % ± 1 point. APPROXIMATION DU PROJET,
# pas un seuil cité d'une source (Garmin n'affiche qu'une jauge sans publier de seuil clinique) :
# choisie pour que l'écart soit lisible sans alarmer — les moyennes de séance observées sur une
# installation réelle vont de 49,99 à 51,31 %.
BALANCE_BAND_PTS = 1.0
BALANCE_CENTRE_PCT = 50.0

RECENT_DAYS = 28            # « récent » = les 4 dernières semaines de la fenêtre
MIN_PER_PERIOD = 2          # séances mini de chaque côté pour annoncer un changement récent/antérieur
MIN_BALANCE_SESSIONS = 5    # séances mesurées mini pour confronter la balance à l'usure
LOW_DYNAMICS_SESSIONS = 5   # sous ce nombre de séances mesurées : confiance « low »
LOW_INSPECTIONS = 3         # sous ce nombre d'inspections : confiance « low »

STRIKE_HINTS = ("heel_strike", "midfoot_forefoot_strike")
STRIKE_LABEL_FR = {"heel_strike": "attaque talon", "midfoot_forefoot_strike": "attaque médio/avant-pied"}

CAVEAT = ("Indice, jamais un diagnostic : cette synthèse ne modifie ni la charge ni le plan d'entraînement. "
          "Une douleur ou une gêne relève d'un avis médical.")

ASSUMPTIONS = {
    "scope": "Séances de course à pied seulement (sport `running` et `trail`) ; marche, randonnée, vélo et autres "
             "sont exclus. Fenêtre glissante de `weeks` semaines (défaut 26).",
    "sources": "Par séance et par grandeur, la valeur est la moyenne pondérée par le temps couvert (`covered_s`) "
               "des échantillons FIT ingérés (`activity_sample`) ; à défaut d'échantillons pour la grandeur, la "
               "clé optionnelle `avg_*` du bloc `arc` de la séance (ARC_KEYS) si elle existe. Une grandeur absente "
               "reste absente : jamais 0, jamais 50 % de balance par défaut.",
    "cadence": "Cadence en PAS/min (deux pieds). Les échantillons sont déjà doublés à l'extraction pour les sports à "
               "pied (`arc_samples.ASSUMPTIONS[\"cadence_doubling\"]`). Repli sur `avg_cadence_spm` du bloc `arc` : "
               "une valeur < 120 est, pour de la course, une cadence PAR PIED non doublée (le piège documenté) — "
               "elle est écartée et comptée dans `notes.cadence_suspect`, jamais corrigée au jugé.",
    "balance_band": f"« Séance hors bande » = |balance − 50 | > {BALANCE_BAND_PTS:g} point. Bande = approximation du "
                    "projet, pas un seuil publié ; ne dit rien d'une blessure.",
    "balance_side": "Le SENS de `stance_time_balance` (quel pied porte le pourcentage) n'est pas établi par le profil "
                    "FIT de `fitparse` (champ `stance_time_balance`, 0,01 %, sans mention gauche/droite) ni par aucune "
                    "source du dépôt : la synthèse parle d'ÉCART à 50 %, jamais de « pied gauche/droit » pour la "
                    "mesure, et ne compare donc jamais le côté de l'usure au côté de la balance "
                    "(`balance_side_verified: false`).",
    "trend": "Tendance par grandeur : moyenne, écart-type, min/max, et — si au moins "
             f"{MIN_PER_PERIOD} séances de chaque côté — différence entre les {RECENT_DAYS} derniers jours de la "
             "fenêtre et la période antérieure. Une différence n'est pas un diagnostic : le bruit d'un capteur de "
             "poignet, la pente, l'allure et la fatigue la font varier.",
    "inspections": "Par paire : décompte des indices d'attaque (`gait_hints`), niveau/côté d'asymétrie de chaque "
                   "inspection, et répétition du MÊME côté (≥ 2 inspections asymétriques du même côté). Des indices "
                   "déduits de photos de semelle, à faible confiance (les chaussures modernes déforment l'usure).",
    "contradictions": "Signalées, jamais arbitrées à l'insu de l'athlète : (1) indices d'attaque différents selon les "
                      "paires ; (2) usure asymétrique vs balance mesurée dans la bande — la MESURE prime, l'usure est "
                      "dite peu fiable ; (3) usure symétrique vs balance mesurée hors bande — la mesure prime aussi ; "
                      "(4) côté d'asymétrie qui change d'une inspection à l'autre sur une même paire.",
    "confidence": f"`confidence` donne les effectifs (séances de course, séances avec dynamique, avec balance, "
                  f"inspections) et un niveau : `none` (0), `low` (< {LOW_DYNAMICS_SESSIONS} séances mesurées ou "
                  f"< {LOW_INSPECTIONS} inspections), `ok` sinon. Un niveau `ok` reste un indice.",
    "not_a_diagnosis": CAVEAT,
}


# ---------------------------------------------------------------------------
# Statistiques élémentaires
# ---------------------------------------------------------------------------


def _finite(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _sd(values: Sequence[float]) -> Optional[float]:
    """Écart-type d'échantillon ; `None` sous 2 valeurs."""
    if len(values) < 2:
        return None
    m = sum(values) / len(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def _fr(value: float) -> str:
    """Nombre au format français (virgule décimale) pour les messages destinés à l'athlète."""
    return f"{value:g}".replace(".", ",")


def _round(value: Optional[float], digits: int) -> Optional[float]:
    return None if value is None else round(value, digits) + 0.0   # `+ 0.0` : jamais « -0.0 » dans le JSON


# Plus petite variation AFFICHABLE par grandeur, en unité SI de l'API (= une unité de la dernière décimale
# montrée par le tableau de bord : 1 ms, 0,01 pt, 0,1 cm, 0,01 pt, 0,01 m, 1 pas/min). Une variation plus petite
# que la moitié de ce pas s'affiche « 0 » : elle est `flat`, jamais dotée d'un signe. La DÉCISION du sens est prise
# ici (testée en palier D), pas dans le JS — un arrondi d'affichage ne doit jamais effacer un signe réel.
DISPLAY_STEP = {"ground_contact_s": 0.001, "stance_balance_pct": 0.01, "vertical_oscillation_m": 0.001,
                "vertical_ratio_pct": 0.01, "step_length_m": 0.01, "cadence_spm": 1.0}


def change_direction(metric: str, change: Optional[float]) -> Optional[str]:
    """`up` / `down` / `flat` (variation sous la moitié du plus petit pas affichable) ; `None` sans variation."""
    if change is None:
        return None
    if abs(change) < DISPLAY_STEP[metric] / 2:
        return "flat"
    return "up" if change > 0 else "down"


# Précision d'affichage par grandeur (SI conservé dans l'API ; le tableau de bord convertit).
_DIGITS = {"ground_contact_s": 4, "stance_balance_pct": 2, "vertical_oscillation_m": 4,
           "vertical_ratio_pct": 2, "step_length_m": 3, "cadence_spm": 1}


# ---------------------------------------------------------------------------
# Une séance → ses grandeurs
# ---------------------------------------------------------------------------


def resolve_session(row: dict, arc: Optional[dict] = None) -> Tuple[dict, dict]:
    """Grandeurs d'UNE séance de course, et leur provenance.

    `row` : moyennes des échantillons FIT par grandeur (clés de `METRICS`, `None` si aucun
    échantillon ne la porte). `arc` : bloc `arc` de la séance (repli, `ARC_KEYS`). Rend
    `(values, notes)` : `values[metric]` = `{"value", "source": "samples"|"arc"}` (absente = grandeur
    non mesurée), `notes` = `{"cadence_suspect": True}` si un repli `avg_cadence_spm` a été écarté."""
    arc = arc or {}
    values: Dict[str, dict] = {}
    notes: Dict[str, Any] = {}
    for metric in METRICS:
        lo, hi = PLAUSIBLE[metric]
        sampled = _finite(row.get(metric))
        if sampled is not None and lo <= sampled <= hi:
            values[metric] = {"value": sampled, "source": "samples"}
            continue
        fallback = _finite(arc.get(ARC_KEYS[metric]))
        if fallback is None:
            continue
        if metric == "cadence_spm" and 0 < fallback < lo:
            notes["cadence_suspect"] = True      # cadence par pied non doublée : écartée, jamais corrigée
            continue
        if lo <= fallback <= hi:
            values[metric] = {"value": fallback, "source": "arc"}
    return values, notes


# ---------------------------------------------------------------------------
# Tendance par grandeur
# ---------------------------------------------------------------------------


def metric_trend(metric: str, points: Iterable[Tuple[str, float]], today: date) -> Optional[dict]:
    """Tendance d'UNE grandeur sur `points` = `(date ISO, valeur par séance)`. `None` sans point."""
    pts = sorted((d, v) for d, v in points if _finite(v) is not None)
    if not pts:
        return None
    digits = _DIGITS[metric]
    values = [v for _, v in pts]
    cutoff = (today - timedelta(days=RECENT_DAYS - 1)).isoformat()
    recent = [v for d, v in pts if d >= cutoff]
    prior = [v for d, v in pts if d < cutoff]
    out: Dict[str, Any] = {
        "n": len(pts), "mean": _round(_mean(values), digits), "sd": _round(_sd(values), digits),
        "min": _round(min(values), digits), "max": _round(max(values), digits),
        "latest": {"date": pts[-1][0], "value": _round(pts[-1][1], digits)},
        "recent_n": len(recent), "prior_n": len(prior),
        "recent_mean": _round(_mean(recent), digits) if recent else None,
        "prior_mean": _round(_mean(prior), digits) if prior else None,
        "change": None,
        "series": [{"date": d, "value": _round(v, digits)} for d, v in pts],
    }
    out["direction"] = None
    if len(recent) >= MIN_PER_PERIOD and len(prior) >= MIN_PER_PERIOD:
        raw_change = _mean(recent) - _mean(prior)
        out["change"] = _round(raw_change, digits)
        out["direction"] = change_direction(metric, raw_change)
    if metric == "stance_balance_pct":
        gaps = [abs(v - BALANCE_CENTRE_PCT) for v in values]
        beyond = sum(1 for g in gaps if g > BALANCE_BAND_PTS)
        out.update({
            "mean_gap_pts": _round(_mean(gaps), 2), "max_gap_pts": _round(max(gaps), 2),
            "beyond_band_n": beyond, "beyond_band_share": _round(beyond / len(gaps), 3),
            "band_pts": BALANCE_BAND_PTS, "band_label": "approximation du projet",
            "side_named": False,
        })
    return out


# ---------------------------------------------------------------------------
# Inspections : indices d'attaque, asymétrie
# ---------------------------------------------------------------------------


def inspection_gait(inspections: Sequence[dict], names: Optional[Dict[str, str]] = None) -> dict:
    """Indices tirés des inspections photo, par paire et au total.

    `inspections` : dicts de `arc_index._inspection_rows` (`gear_id`, `date`, `condition`,
    `asymmetry{level, side}`, `gait_hints`…), ordre libre."""
    names = names or {}
    by_gear: Dict[str, List[dict]] = {}
    for insp in inspections:
        by_gear.setdefault(insp.get("gear_id") or "?", []).append(insp)
    tally_all: Dict[str, int] = {}
    pairs = []
    for gear_id, rows in by_gear.items():
        rows = sorted(rows, key=lambda r: (r.get("date") or "", r.get("path") or ""))
        tally: Dict[str, int] = {}
        asymmetry = []
        strike_sets: List[List[str]] = []      # indices d'ATTAQUE seulement (pronation/supination exclus), par inspection
        for r in rows:
            strikes_here = sorted({h for h in (r.get("gait_hints") or []) if h in STRIKE_HINTS})
            if strikes_here:
                strike_sets.append(strikes_here)
            for hint in r.get("gait_hints") or []:
                tally[hint] = tally.get(hint, 0) + 1
                tally_all[hint] = tally_all.get(hint, 0) + 1
            asym = r.get("asymmetry") or {}
            if asym.get("level"):
                item = {"date": r.get("date"), "level": asym["level"]}
                if asym.get("side"):
                    item["side"] = asym["side"]
                asymmetry.append(item)
        sides = [a["side"] for a in asymmetry if a["level"] != "none" and a.get("side")]
        by_side = {s: sides.count(s) for s in set(sides)}
        top_side = max(by_side, key=by_side.get) if by_side else None
        repeats = ({"side": top_side, "count": by_side[top_side], "of": len(sides)}
                   if top_side and by_side[top_side] >= 2 else None)
        strike = {h: tally[h] for h in STRIKE_HINTS if h in tally}
        dominant = None
        if strike:
            best = max(strike.values())
            leaders = [h for h, c in strike.items() if c == best]
            dominant = leaders[0] if len(leaders) == 1 else None
        latest = rows[-1]
        pairs.append({
            "gear_id": gear_id, "name": names.get(gear_id) or gear_id, "n": len(rows),
            "strike_hints": dict(sorted(tally.items())),
            "dominant_strike": dominant,
            "latest_strike": [h for h in (latest.get("gait_hints") or []) if h in STRIKE_HINTS],
            "strike_sets": strike_sets,
            "latest_date": latest.get("date"),
            "asymmetry": asymmetry,
            "asymmetry_repeats": repeats,
            "asymmetry_side_changes": len(by_side) > 1,
        })
    pairs.sort(key=lambda p: (p["name"].casefold(), p["gear_id"]))
    return {"n": len(inspections), "pairs": pairs, "strike_hint_tally": dict(sorted(tally_all.items()))}


# ---------------------------------------------------------------------------
# Contradictions
# ---------------------------------------------------------------------------


def find_contradictions(dynamics: Dict[str, Optional[dict]], insp: dict) -> List[dict]:
    """Désaccords entre les indices d'inspection, ou entre usure et mesure. Jamais arbitrés en
    silence : chaque entrée dit ce qui diffère et, quand une mesure existe, que la mesure prime."""
    out: List[dict] = []
    pairs = insp.get("pairs") or []

    # 1. Indices d'attaque différents selon les paires (dernière inspection de chaque paire).
    latest: Dict[str, List[str]] = {}
    for p in pairs:
        strikes = p.get("latest_strike") or []
        if strikes:
            latest[p["name"]] = strikes
    heel = sorted(n for n, s in latest.items() if "heel_strike" in s)
    fore = sorted(n for n, s in latest.items() if "midfoot_forefoot_strike" in s)
    if heel and fore and set(heel) != set(fore):
        out.append({
            "code": "strike_hint_differs_across_pairs", "severity": "info",
            "message": ("Indices d'attaque différents selon les paires : "
                        f"{', '.join(heel)} ({STRIKE_LABEL_FR['heel_strike']}) ; "
                        f"{', '.join(fore)} ({STRIKE_LABEL_FR['midfoot_forefoot_strike']}). "
                        "L'attaque varie avec la chaussure, l'allure et le terrain, ou l'un des indices est faux : "
                        "aucun des deux n'est une mesure."),
            "evidence": {"heel_strike": heel, "midfoot_forefoot_strike": fore},
            "resolution": "unresolved",
        })

    # 1 bis. Indice d'attaque qui change au sein d'une même paire.
    # Seuls les indices d'ATTAQUE comptent (pronation/supination n'en sont pas). Changement d'une inspection
    # à l'autre (ensembles différents) != deux indices d'attaque dans UNE même inspection (formulation distincte).
    for p in pairs:
        sets = p.get("strike_sets") or []
        label = lambda s: " + ".join(STRIKE_LABEL_FR[h] for h in s)
        if len({tuple(s) for s in sets}) > 1:
            out.append({
                "code": "strike_hint_changes_within_pair", "severity": "info",
                "message": (f"{p['name']} : l'indice d'attaque change d'une inspection à l'autre "
                            f"({' ; '.join(dict.fromkeys(label(s) for s in sets))}) — peu fiable."),
                "evidence": {"gear_id": p["gear_id"], "strike_sets": sets},
                "resolution": "unresolved",
            })
        if any(len(s) > 1 for s in sets):
            out.append({
                "code": "strike_hints_conflict_in_inspection", "severity": "info",
                "message": (f"{p['name']} : une même inspection note à la fois l'attaque talon et l'attaque "
                            "médio/avant-pied — lecture ambiguë de la photo, à prendre avec prudence."),
                "evidence": {"gear_id": p["gear_id"], "strike_sets": [s for s in sets if len(s) > 1]},
                "resolution": "unresolved",
            })

    # 2/3. Usure vs balance mesurée — la mesure prime.
    balance = dynamics.get("stance_balance_pct")
    if balance and balance["n"] >= MIN_BALANCE_SESSIONS and insp.get("n"):
        asym_levels = [a["level"] for p in pairs for a in p["asymmetry"]]
        worn = [lv for lv in asym_levels if lv != "none"]
        gap = balance["mean_gap_pts"]
        if worn and gap <= BALANCE_BAND_PTS:
            out.append({
                "code": "wear_asymmetry_vs_symmetric_balance", "severity": "info",
                "message": (f"Usure asymétrique sur {len(worn)} inspection(s), mais la balance du temps de contact "
                            f"mesurée reste proche de 50 % (écart moyen {_fr(gap)} pt sur {balance['n']} séances, dans "
                            "la bande du projet) : la mesure prime, l'asymétrie d'usure est peu fiable "
                            "(semelle, terrain, pose du pied au repos)."),
                "evidence": {"inspections_asymmetric": len(worn), "mean_gap_pts": gap, "sessions": balance["n"]},
                "resolution": "measure_wins",
            })
        elif asym_levels and not worn and gap > BALANCE_BAND_PTS:
            out.append({
                "code": "symmetric_wear_vs_measured_imbalance", "severity": "info",
                "message": (f"Usure symétrique constatée, mais la balance mesurée s'écarte de 50 % "
                            f"(écart moyen {_fr(gap)} pt sur {balance['n']} séances, hors de la bande du projet) : la "
                            "mesure prime — l'absence d'asymétrie visible sur la semelle ne l'exclut pas. "
                            "Le côté du pourcentage n'étant pas établi, on ne dit pas de quel pied il s'agit."),
                "evidence": {"mean_gap_pts": gap, "sessions": balance["n"]},
                "resolution": "measure_wins",
            })

    # 4. Côté d'asymétrie qui change d'une inspection à l'autre.
    for p in pairs:
        if p.get("asymmetry_side_changes"):
            out.append({
                "code": "asymmetry_side_changes", "severity": "info",
                "message": (f"{p['name']} : le côté le plus usé change d'une inspection à l'autre — "
                            "une asymétrie qui ne se répète pas du même côté est peu fiable."),
                "evidence": {"gear_id": p["gear_id"], "asymmetry": p["asymmetry"]},
                "resolution": "unresolved",
            })
    return out


# ---------------------------------------------------------------------------
# Synthèse
# ---------------------------------------------------------------------------


def _level(n: int, low_below: int) -> str:
    return "none" if n == 0 else "low" if n < low_below else "ok"


def gait_summary(sessions: Sequence[dict], inspections: Sequence[dict], today: date, weeks: int,
                 names: Optional[Dict[str, str]] = None) -> dict:
    """Synthèse « Foulée ». `sessions` : une entrée par séance de course de la fenêtre,
    `{date, activity_id, name, sport, values: {metric: {value, source}}, notes}` (voir
    `resolve_session`). `inspections` : toutes les inspections indexées (la fenêtre ne s'applique
    qu'aux séances : une inspection d'il y a un an renseigne encore la paire)."""
    points: Dict[str, List[Tuple[str, float]]] = {m: [] for m in METRICS}
    cadence_suspect = 0
    from_arc = {m: 0 for m in METRICS}
    for s in sessions:
        if (s.get("notes") or {}).get("cadence_suspect"):
            cadence_suspect += 1
        for metric, item in (s.get("values") or {}).items():
            points[metric].append((s["date"], item["value"]))
            if item.get("source") == "arc":
                from_arc[metric] += 1
    dynamics = {m: metric_trend(m, points[m], today) for m in METRICS}
    insp = inspection_gait(inspections, names)
    with_dyn = sum(1 for s in sessions if any(k in (s.get("values") or {}) for k in METRICS if k != "cadence_spm"))
    with_balance = sum(1 for s in sessions if "stance_balance_pct" in (s.get("values") or {}))
    return {
        "window": {"weeks": weeks, "since": (today - timedelta(days=weeks * 7 - 1)).isoformat(),
                   "until": today.isoformat()},
        "sport_scope": ["running", "trail"],
        "dynamics": dynamics,
        "inspections": insp,
        "contradictions": find_contradictions(dynamics, insp),
        "confidence": {
            "running_sessions": len(sessions),
            "sessions_with_dynamics": with_dyn,
            "sessions_with_balance": with_balance,
            "inspections": insp["n"],
            "pairs_inspected": len(insp["pairs"]),
            "dynamics_level": _level(with_dyn, LOW_DYNAMICS_SESSIONS),
            "inspections_level": _level(insp["n"], LOW_INSPECTIONS),
        },
        "balance_side_verified": False,
        "notes": {"cadence_suspect": cadence_suspect,
                  "values_from_arc_block": {m: n for m, n in from_arc.items() if n}},
        "caveat": CAVEAT,
    }
