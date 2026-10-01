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

Un message contenant « fatigu » joue la démonstration des captures de la doc (bilan matinal,
trace, carte d'approbation). Un message contenant « lent » fait attendre le tour (annulable) : c'est ce qui permet de
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

# Démonstration (captures de la doc, workspace `tests/lib/synthetic.py` au 2026-09-29 : côtes
# prévues ce jour-là). Charge distincte du scénario des tests.
DEMO_INPUT = {"workouts": [{"date": "2026-09-29", "name": "EF 45 min", "duration_min": 45},
                           {"date": "2026-10-01", "name": "Côtes 8 × 90 s", "duration_min": 60}]}
DEMO_SUMMARY = "Mardi 29 septembre : footing EF 45 min, côtes jeudi"
DEMO_DIFF = [
    {"op": "-", "text": "Mardi : côtes 8 × 90 s"},
    {"op": "+", "text": "Mardi : EF 45 min"},
    {"op": " ", "text": "Mercredi : repos"},
    {"op": "+", "text": "Jeudi : côtes 8 × 90 s (si le bilan du matin remonte)"},
]


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
            demo = DEMO_SUMMARY in user_message
            if self._call_schedule(ctx, *((DEMO_INPUT, DEMO_SUMMARY, DEMO_DIFF) if demo else ())) != "allow":
                emit("text_delta", {"text": "Appel non autorisé par la politique."})
            finish("end_turn")
            return

        if "fatigu" in text:
            self._demo_morning_check(ctx, finish)
            return

        emit("text_delta", {"text": "Je regarde ton plan de la semaine. "})
        emit("tool_start", {"id": "t1", "name": "fs.read", "summary": "Lecture de planning/active_objective.md"})
        emit("tool_end", {"id": "t1", "ok": True, "summary": "Objectif lu"})
        emit("text_delta", {"text": "Voici mon analyse. "})
        emit("file_written", {"path": DECISION_PATH})

        if "bilan" in text:
            # Réponse riche (titre, tableau, bloc ```arc recopié comme le ferait un modèle
            # trop littéral) : sert à vérifier le rendu de la page sans modèle.
            for chunk in ("\n\n## Bilan de la semaine\n\n", "| Jour | Séance | Durée |\n|---|---|---|\n",
                          "| Lun | EF | 45 min |\n| Mer | Fractionné | 1 h 05 |\n\n",
                          "```arc\n{\"type\": \"week\", \"load\": 412}\n```\n\n",
                          "**Prochaine étape** : sortie longue samedi."):
                emit("text_delta", {"text": chunk})
            finish("end_turn")
            return

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

    def _demo_morning_check(self, ctx: TurnContext, finish) -> None:
        """Scénario de démonstration (captures de la doc) : bilan matinal, trace, proposition.

        Valeurs fictives, cohérentes entre elles ; aucune donnée lue sur disque.
        """
        emit = ctx.emit
        steps = (
            ("d1", "skill", "Chargement de la compétence today", "Terminé"),
            ("d2", "fs.read", "Lecture de planning/Semaine_2026-09-28.md", "Séance du jour : côtes 8 × 90 s"),
            ("d3", "mcp:garmin.get_hrv_data", "Garmin : get_hrv_data", "HRV 52 ms (base 7 j : 63 ms)"),
            ("d4", "mcp:garmin.get_rhr_day", "Garmin : get_rhr_day", "FC de repos 54 bpm (+5)"),
            ("d5", "mcp:garmin.get_training_readiness", "Garmin : get_training_readiness", "Readiness 38 (faible)"),
            ("d6", "web.fetch", "Consultation de wttr.in (météo du lieu d'entraînement)", "16 °C, averses en soirée"),
        )
        emit("text_delta", {"text": "Je fais ton bilan du matin avant de décider.", "part": "n1"})
        for sid, name, summary, result in steps[:2]:
            emit("tool_start", {"id": sid, "name": name, "summary": summary})
            emit("tool_end", {"id": sid, "ok": True, "summary": result})
        emit("text_delta", {"text": "Séance exigeante prévue : je vérifie HRV, FC de repos et readiness.",
                            "part": "n2"})
        for sid, name, summary, result in steps[2:]:
            emit("tool_start", {"id": sid, "name": name, "summary": summary})
            emit("tool_end", {"id": sid, "ok": True, "summary": result})
        emit("file_written", {"path": "planning/2026-09-29_decision_readiness-basse.md"})
        for chunk in (
            "**Bilan du matin** — les trois signaux vont dans le même sens que ton ressenti :\n\n",
            "| Indicateur | Ce matin | Repère |\n|---|---|---|\n",
            "| HRV | 52 ms | base 63 ms |\n| FC de repos | 54 bpm | +5 bpm |\n| Readiness | 38 | faible |\n\n",
            "Des côtes sur cette fatigue apportent peu et coûtent cher en récupération. ",
            "**Je te propose** une sortie en endurance fondamentale de 45 min aujourd'hui, ",
            "et de décaler les côtes à jeudi si le bilan remonte.\n\n",
            "Créneau conseillé : **12 h 15 – 13 h 00** (sec, 16 °C).",
        ):
            emit("text_delta", {"text": chunk, "part": "r1"})
        outcome = self._call_schedule(ctx, DEMO_INPUT, DEMO_SUMMARY, DEMO_DIFF)
        if outcome == "pending":
            emit("text_delta", {"text": "La proposition attend ta confirmation (page ou notification).",
                                "part": "r2"})
            finish("pending_approval")
            return
        emit("text_delta", {"text": "C'est fait : la séance est au calendrier." if outcome == "allow"
                            else "D'accord, je garde le plan tel quel.", "part": "r2"})
        finish("end_turn")

    def _call_schedule(self, ctx: TurnContext, tool_input: dict = TOOL_INPUT, summary: str = SUMMARY,
                       diff: list = DIFF) -> str:
        """Passe l'appel par la politique puis l'approbation ; renvoie allow | deny | pending."""
        verdict = ctx.decide(TOOL, tool_input)
        if verdict == "ask":
            verdict = ctx.request_approval(TOOL, tool_input, summary, diff)
        if verdict == "allow":
            ctx.emit("tool_start", {"id": "t2", "name": TOOL, "summary": "Planification de la séance"})
            ctx.emit("tool_end", {"id": "t2", "ok": True, "summary": "Séance planifiée (simulation)"})
            return "allow"
        return "pending" if verdict == "pending" else "deny"
