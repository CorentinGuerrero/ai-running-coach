#!/usr/bin/env python3
"""Serveur MCP « intervals » factice, pour le palier C (story source
intervals.icu, #68).

Même protocole, même journal d'appels, même mécanique de scripting par cas
d'éval que `stub_garmin_mcp.py` (partagés via `mcp_stub_common.py`) — seuls la
liste d'outils et les données canned changent, pour coller à une source de
données alternative.

**Liste d'outils et FORME de réponse : VÉRIFIÉES (#68, revue PR #116)** contre
le code source du serveur réellement installé par le projet
(`./install.sh --source intervals`, voir `AGENTS.md` → « Backends MCP ») :
[`eddmann/intervals-icu-mcp`](https://github.com/eddmann/intervals-icu-mcp),
commit `cb91d4a` (`src/intervals_icu_mcp/tools/*.py`, `response_builder.py`).

Deux points de fidélité qui ont changé depuis une première version non
vérifiée de ce stub :

1. **Enveloppe `{"data": ..., "metadata": {...}}`** (et `"analysis"` quand le
   vrai outil en produit une) — `ResponseBuilder.build_response` l'applique à
   CHAQUE outil, contrairement à `garmin_mcp` qui rend ses résultats à plat.
   Une assertion `payload["data"][...]` doit fonctionner contre ce stub
   exactement comme contre le vrai serveur.
2. **Formes imbriquées fidèles** par outil (`heart.resting_hr`, `sleep.*`,
   `subjective.readiness`, `fitness_metrics.ctl.value`...) — jamais un
   raccourci plat qui n'existe pas côté serveur réel.

**Scriptable par cas d'éval (#26)**, identique à `stub_garmin_mcp.py` :
`[stub.intervals.<outil>] file = "…json"` ou `error = "401" | "timeout" | "empty"`.
Note de fidélité sur `error = "empty"` : `mcp_stub_common.resolve_content` vide
tout le gabarit `default` (ici l'enveloppe entière), donc `{}` — pas
`{"data": {}, "metadata": {...}}` comme le rendrait le vrai serveur pour un
résultat vide. Ce mécanisme est partagé avec `stub_garmin_mcp.py` ; aucun cas
d'éval de cette story ne scripte `error = "empty"` contre `intervals`, donc
l'écart n'affecte aucune assertion existante — à corriger dans
`mcp_stub_common.py` si un futur cas en a besoin.

JSON-RPC 2.0 sur stdin/stdout, une requête par ligne. Bibliothèque standard.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mcp_stub_common as common

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

TODAY = date.today()


def _day(offset: int) -> str:
    return (TODAY - timedelta(days=offset)).isoformat()


def _envelope(data, *, query_type: str, analysis=None, metadata=None):
    """Reproduit `ResponseBuilder.build_response` : `data` (+ `analysis`
    optionnelle) sous une `metadata` qui porte toujours `query_type` (le
    vrai `fetched_at` horodaté n'est pas reproduit — sans intérêt pour les
    assertions des cas d'éval, qui ne portent jamais sur un timestamp)."""
    meta = {"query_type": query_type}
    if metadata:
        meta.update(metadata)
    envelope = {"data": data, "metadata": meta}
    if analysis:
        envelope["analysis"] = analysis
    return envelope


# Données synthétiques : un athlète reposé, sans signal d'alerte — même
# posture que le stub garmin, pour que basculer `[data].source` entre les
# deux ne change rien au comportement par défaut d'un scénario.
CANNED = {
    "get_wellness_for_date": _envelope(
        {
            "date": _day(0),
            "sleep": {"duration_seconds": 25800, "score": 78},
            "heart": {"hrv_rmssd": 62.0, "resting_hr": 49},
            # Valeur manuelle du jour — PAS un score de readiness calculé
            # (aucun outil de ce serveur n'en produit un, voir AGENTS.md).
            "subjective": {"readiness": 71},
        },
        query_type="wellness_for_date",
    ),
    # Forme vérifiée (`tools/wellness.py::get_wellness_data`) : `data.wellness_data`
    # (liste) + `data.count` — PAS une liste nue à la racine de `data` comme une
    # version antérieure non vérifiée de ce stub le rendait.
    "get_wellness_data": _envelope(
        {
            "wellness_data": [{
                "date": _day(0),
                "sleep": {"duration_seconds": 25800, "score": 78},
                "heart": {"hrv_rmssd": 62.0, "resting_hr": 49},
                "subjective": {"readiness": 71},
            }],
            "count": 1,
        },
        query_type="wellness_data",
    ),
    "get_recent_activities": _envelope(
        {
            "activities": [{
                "id": "i99000001",
                "name": "Sortie longue",
                "start_date": f"{_day(2)}T12:05:00",
                "type": "Run",
                "distance_meters": 24800.0,
                "moving_time_seconds": 9660.0,
                "elevation_gain_meters": 890.0,
                "average_heartrate": 141,
            }],
            "count": 1,
        },
        query_type="recent_activities",
    ),
    "get_activity_details": _envelope(
        {
            "id": "i99000001", "name": "Sortie longue", "type": "Run",
            "start_date": f"{_day(2)}T12:05:00",
            "distance_meters": 24800.0, "moving_time_seconds": 9660.0,
            "elevation_gain_meters": 890.0,
            "heart_rate": {"average": 141, "max": 168},
        },
        query_type="activity_details",
    ),
    # Fenêtre vide (aucun événement) : forme réelle du serveur pour ce cas
    # précis — `data.events` (jamais `events_by_date`, qui n'apparaît que
    # lorsque la liste n'est pas vide).
    "get_calendar_events": _envelope(
        {"events": [], "count": 0, "date_range": {"oldest": _day(0), "newest": _day(-7)}},
        query_type="calendar_events",
    ),
    "get_upcoming_workouts": _envelope(
        {"workouts": [], "count": 0},
        query_type="upcoming_workouts",
    ),
    "get_event": _envelope(
        {"id": 123456, "date": _day(0), "name": "Endurance 60 min", "category": "WORKOUT"},
        query_type="get_event",
    ),
    "get_athlete_profile": _envelope(
        {"profile": {"id": "i0", "name": "Athlete"}, "fitness": {"ctl": 42.0, "atl": 38.0, "tsb": 4.0}},
        query_type="athlete_profile",
    ),
    "get_fitness_summary": _envelope(
        {
            "athlete_name": "Athlete",
            "fitness_metrics": {
                "ctl": {"value": 42.0, "description": "Chronic Training Load (Fitness)"},
                "atl": {"value": 38.0, "description": "Acute Training Load (Fatigue)"},
                "tsb": {"value": 4.0, "description": "Training Stress Balance (Form)"},
            },
        },
        query_type="fitness_summary",
    ),
}

TOOLS = [
    ("get_wellness_for_date", "Wellness (HRV, FC repos, sommeil, valeur manuelle du jour) pour une date."),
    ("get_wellness_data", "Wellness entre deux dates."),
    ("get_recent_activities", "Dernières activités enregistrées."),
    ("get_activity_details", "Détail d'une activité."),
    ("get_calendar_events", "Événements planifiés entre deux dates."),
    ("get_upcoming_workouts", "Séances planifiées à venir."),
    ("get_event", "Détail d'un événement planifié."),
    ("get_athlete_profile", "Profil de l'athlète."),
    ("get_fitness_summary", "CTL/ATL/forme courants."),
    ("create_event", "Planifie une séance dans le calendrier intervals.icu."),
    ("update_event", "Modifie un événement planifié existant (event_id requis)."),
    ("delete_event", "Supprime un événement planifié."),
    ("bulk_create_events", "Planifie plusieurs séances en un appel."),
]


def result_for(name: str, arguments: dict):
    if name in CANNED:
        return CANNED[name]
    if name in ("create_event", "update_event", "bulk_create_events"):
        # Formes réelles vérifiées (event_management.py) : un event unique
        # écho des champs fournis pour create_event/update_event, une liste
        # `events` pour bulk_create_events — jamais de `workout_doc` en
        # retour (voir `skills/intervals-icu-best-practices/SKILL.md`).
        if name == "bulk_create_events":
            return _envelope({"events": []}, query_type="bulk_create_events")
        echoed = {k: v for k, v in (arguments or {}).items() if k != "event_id"}
        return _envelope({"id": arguments.get("event_id", 123456), **echoed}, query_type=name)
    if name == "delete_event":
        return _envelope(
            {"event_id": (arguments or {}).get("event_id"), "deleted": True},
            query_type="delete_event",
        )
    return _envelope({}, query_type=name)


def main() -> int:
    handle = common.make_handler(
        server_name="intervals", tools=TOOLS, result_for=result_for, fixtures_dir=FIXTURES_DIR,
    )
    return common.serve(handle)


if __name__ == "__main__":
    raise SystemExit(main())
