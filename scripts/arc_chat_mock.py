#!/usr/bin/env python3
"""Backend « mock » du chat coach : tours scriptés, déterministes, sans modèle ni réseau.

Sert aux tests du service et au développement de l'interface (`[chat].backend =
"mock"`). Chaque tour joue le même scénario en français :

  1. `text_delta` (introduction) ;
  2. `tool_start` / `tool_end` pour une lecture (`fs.read`, autorisée) ;
  3. `file_written` pour un fichier de décision — annoncé seulement, RIEN n'est écrit sur disque ;
  4. si le message parle de planification (« planifi », « garmin », « séance ») : appel
     `mcp:garmin.schedule_workouts` passé par `ctx.decide` puis `ctx.request_approval`,
     avec réaction à allow / deny / pending ;
  5. `usage` (coût faible) puis `done`.

Un message contenant « lent » fait attendre le tour (annulable) : c'est ce qui permet de
tester le 409 (tour déjà en cours) et l'interruption. Un message `[approbation] …` (reprise
après approbation tardive) exécute directement l'appel pré-approuvé.

Réglages optionnels dans `[chat]` : `mock_cost_eur` (défaut 0.01), `mock_slow_s` (défaut 5).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_chat_backend import ChatBackend, TurnContext  # noqa: E402

TOOL = "mcp:garmin.schedule_workouts"
# Contenu FIXE : l'approbation tardive ne vaut que pour cette charge exacte (payload_hash).
TOOL_INPUT = {"workouts": [{"date": "2026-10-01", "name": "EF 45 min", "duration_min": 45}]}
SUMMARY = "Jeudi 1er octobre : footing EF 45 min"
DIFF = [
    {"op": "-", "text": "Jeudi : fractionné 8 × 400 m"},
    {"op": "+", "text": "Jeudi : EF 45 min"},
    {"op": " ", "text": "Vendredi : repos"},
]
DECISION_PATH = "planning/2026-10-01_decision_mock.md"


class MockBackend(ChatBackend):
    name = "mock"

    def run_turn(self, ctx: TurnContext, user_message: str) -> None:
        emit = ctx.emit
        text = user_message.lower()
        cost = float(self.config.get("mock_cost_eur", 0.01))

        def finish(reason: str) -> None:
            emit("usage", {"input_tokens": 120, "output_tokens": 40, "cache_read_tokens": 0, "cost_eur": cost})
            emit("done", {"reason": reason})

        if user_message.startswith("[approbation]"):
            emit("text_delta", {"text": "Reprise après approbation. "})
            if self._call_schedule(ctx) != "allow":
                emit("text_delta", {"text": "Appel non autorisé par la politique."})
            finish("end_turn")
            return

        emit("text_delta", {"text": "Je regarde ton plan de la semaine. "})
        emit("tool_start", {"id": "t1", "name": "fs.read", "summary": "Lecture de planning/active_objective.md"})
        emit("tool_end", {"id": "t1", "ok": True, "summary": "Objectif lu"})
        emit("text_delta", {"text": "Voici mon analyse. "})
        emit("file_written", {"path": DECISION_PATH})

        if "lent" in text:
            emit("text_delta", {"text": "Je réfléchis longuement… "})
            slow = float(self.config.get("mock_slow_s", 5))
            if ctx.cancelled.wait(slow):
                emit("done", {"reason": "interrupted"})
                return

        if any(word in text for word in ("planifi", "garmin", "séance", "seance")):
            outcome = self._call_schedule(ctx)
            if outcome == "pending":
                emit("text_delta", {"text": "La proposition attend ta confirmation (page ou notification)."})
                finish("pending_approval")
                return
            if outcome == "allow":
                emit("text_delta", {"text": "C'est fait : la séance est au calendrier."})
            else:
                emit("text_delta", {"text": "D'accord, je ne modifie rien."})
        else:
            emit("text_delta", {"text": "Rien à modifier pour l'instant."})
        finish("end_turn")

    def _call_schedule(self, ctx: TurnContext) -> str:
        """Passe l'appel par la politique puis l'approbation ; renvoie allow | deny | pending."""
        verdict = ctx.decide(TOOL, TOOL_INPUT)
        if verdict == "ask":
            verdict = ctx.request_approval(TOOL, TOOL_INPUT, SUMMARY, DIFF)
        if verdict == "allow":
            ctx.emit("tool_start", {"id": "t2", "name": TOOL, "summary": "Planification de la séance"})
            ctx.emit("tool_end", {"id": "t2", "ok": True, "summary": "Séance planifiée (simulation)"})
            return "allow"
        return "pending" if verdict == "pending" else "deny"
