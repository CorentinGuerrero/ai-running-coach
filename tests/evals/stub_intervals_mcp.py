#!/usr/bin/env python3
"""Serveur MCP « intervals » factice, pour le palier C (story source
intervals.icu, #68).

Même protocole, même journal d'appels, même mécanique de scripting par cas
d'éval que `stub_garmin_mcp.py` (partagés via `mcp_stub_common.py`) — seuls la
liste d'outils et les données canned changent, pour coller à une source de
données alternative.

**Liste d'outils : VÉRIFIÉE (#68), plus une hypothèse.** Le serveur retenu par
le projet (`./install.sh --source intervals`, voir `AGENTS.md` → « Backends
MCP ») est le serveur communautaire
[`eddmann/intervals-icu-mcp`](https://github.com/eddmann/intervals-icu-mcp).
Les noms ci-dessous viennent directement de son code source
(`src/intervals_icu_mcp/tools/*.py`, branche `main` au moment de cette story) —
snake_case, PAS le kebab-case d'une version antérieure de ce stub (héritée
d'une hypothèse non vérifiée avant #68) : `get_wellness_for_date`,
`get_wellness_data`, `get_recent_activities`, `get_activity_details`,
`get_calendar_events`, `get_upcoming_workouts`, `get_athlete_profile`,
`get_fitness_summary`, `create_event`, `update_event`, `delete_event`,
`bulk_create_events`. On n'en reprend ici qu'un sous-ensemble plausible pour ce
que les agents `coach`/`medical` consomment aujourd'hui côté Garmin (table de
correspondance complète : `AGENTS.md`).

**Scriptable par cas d'éval (#26)**, identique à `stub_garmin_mcp.py` :
`[stub.intervals.<outil>] file = "…json"` ou `error = "401" | "timeout" | "empty"`.

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


# Données synthétiques : un athlète reposé, sans signal d'alerte — même
# posture que le stub garmin, pour que basculer `[data].source` entre les
# deux ne change rien au comportement par défaut d'un scénario. Forme
# imbriquée fidèle à `ResponseBuilder`/`get_wellness_for_date` du serveur réel
# (sleep/heart/subjective groupés) — PAS le get_hrv_data/get_rhr_day plats de
# garmin_mcp : c'est précisément ce qui matérialise, dans le stub, qu'un seul
# appel intervals.icu couvre ce que trois appels Garmin couvrent (AGENTS.md).
CANNED = {
    "get_wellness_for_date": {
        "date": _day(0),
        "sleep": {"duration_seconds": 25800, "score": 78},
        "heart": {"hrv_rmssd": 62.0, "resting_hr": 49},
        # Auto-déclaré par l'athlète — PAS un score de readiness calculé
        # (aucun outil de ce serveur n'en produit un, voir AGENTS.md).
        "subjective": {"readiness": 71},
    },
    "get_wellness_data": [{
        "date": _day(0),
        "sleep": {"duration_seconds": 25800, "score": 78},
        "heart": {"hrv_rmssd": 62.0, "resting_hr": 49},
        "subjective": {"readiness": 71},
    }],
    "get_recent_activities": {
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
    "get_activity_details": {"id": "i99000001", "stub": True},
    "get_calendar_events": [],
    "get_upcoming_workouts": [],
    "get_event": {"stub": True},
    "get_athlete_profile": {"id": "i0", "name": "Athlete"},
    "get_fitness_summary": {"ctl": 42.0, "atl": 38.0, "form": 4.0},
}

TOOLS = [
    ("get_wellness_for_date", "Wellness (HRV, FC repos, sommeil, ressenti auto-déclaré) pour une date."),
    ("get_wellness_data", "Wellness entre deux dates."),
    ("get_recent_activities", "Dernières activités enregistrées."),
    ("get_activity_details", "Détail d'une activité."),
    ("get_calendar_events", "Événements planifiés entre deux dates."),
    ("get_upcoming_workouts", "Séances planifiées à venir."),
    ("get_event", "Détail d'un événement planifié."),
    ("get_athlete_profile", "Profil de l'athlète."),
    ("get_fitness_summary", "CTL/ATL/forme courants."),
    ("create_event", "Planifie une séance dans le calendrier intervals.icu."),
    ("update_event", "Modifie un événement planifié."),
    ("delete_event", "Supprime un événement planifié."),
    ("bulk_create_events", "Planifie plusieurs séances en un appel."),
]


def result_for(name: str, arguments: dict):
    if name in CANNED:
        return CANNED[name]
    if name.startswith(("create_", "update_", "delete_", "bulk_")):
        return {"status": "ok", "stub": True, "tool": name, "received": arguments}
    return {"status": "ok", "stub": True, "tool": name, "data": []}


def main() -> int:
    handle = common.make_handler(
        server_name="intervals", tools=TOOLS, result_for=result_for, fixtures_dir=FIXTURES_DIR,
    )
    return common.serve(handle)


if __name__ == "__main__":
    raise SystemExit(main())
