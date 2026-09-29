#!/usr/bin/env python3
"""Contrat commun du chat coach : événements, noms d'outils canoniques, backends.

Le service `scripts/arc_chat.py` parle au navigateur avec un protocole unique
(événements SSE ci-dessous) ; chaque backend — `mock`, `claude` (Claude Agent SDK,
`arc_chat_claude.py`), `opencode` (serveur OpenCode, `arc_chat_opencode.py`) —
traduit son propre flux vers ce protocole. Le navigateur ne sait jamais quel
modèle tourne derrière.

Les outils sont ramenés à des noms **canoniques** avant de passer par la
politique de permissions (`config/chat-policy.toml`) : les deux harnais
nomment différemment le même outil (`Write` / `write`,
`mcp__garmin__schedule_workouts` / `garmin_schedule_workouts`…).

Bibliothèque standard uniquement (CONTRIBUTING.md). Seul `arc_chat_claude.py`
importe un paquet tiers (`claude-agent-sdk`), paresseusement.
"""

from __future__ import annotations

import hashlib
import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Événements (SSE : `event: <type>\ndata: <json>\n\n`)
# ---------------------------------------------------------------------------
#
#   text_delta         {"text": str}
#   tool_start         {"id": str, "name": str (canonique), "summary": str}
#   tool_end           {"id": str, "ok": bool, "summary": str}
#   approval_request   {"approval_id": str, "tool": str, "summary": str,
#                       "diff": [{"op": "-"|"+"|" ", "text": str}], "expires_at": iso8601}
#   approval_resolved  {"approval_id": str, "decision": "allow"|"deny"|"pending"|"expired"|"cancelled"|"unexecuted"}
#   file_written       {"path": str (relatif au workspace)}
#   usage              {"input_tokens": int, "output_tokens": int,
#                       "cache_read_tokens": int, "cost_eur": float}
#   done               {"reason": "end_turn"|"interrupted"|"budget"|"max_turns"|"pending_approval"}
#   error              {"message": str (français, lisible par l'athlète)}

EVENT_TYPES = (
    "text_delta", "tool_start", "tool_end", "approval_request", "approval_resolved",
    "file_written", "usage", "done", "error",
)

# ---------------------------------------------------------------------------
# Noms d'outils canoniques
# ---------------------------------------------------------------------------
#
#   fs.read      {"path": str}
#   fs.write     {"path": str}            (création, écrasement ou édition)
#   fs.list      {"path": str}            (glob/grep/ls)
#   shell        {"command": str}
#   web.fetch    {"url": str}
#   web.search   {"query": str}
#   task         {"agent": str}           (délégation à un sous-agent)
#   skill        {"name": str}
#   mcp:<serveur>.<outil>                 (ex. "mcp:garmin.schedule_workouts")
#   other:<nom>                           (tout le reste — refusé par défaut)

CANONICAL_PREFIXES = ("fs.", "shell", "web.", "task", "skill", "mcp:", "other:")

Decision = str  # "allow" | "deny" | "pending"


def payload_hash(tool: str, tool_input: dict) -> str:
    """Empreinte stable d'un appel d'outil : lie une approbation à UN contenu exact."""
    canonical = json.dumps({"tool": tool, "input": tool_input}, sort_keys=True,
                           ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Ajouté au prompt système par chaque backend (langue de sortie inchangée :
# AGENTS.md et la configuration décident).
SYSTEM_ADDENDUM = """\
Tu réponds à l'athlète via l'interface web « Coach » du tableau de bord.
- Toute écriture vers Garmin ou intervals.icu est soumise à l'approbation explicite
  de l'athlète : propose le changement, appelle l'outil, et l'interface affichera une
  carte de confirmation. N'affirme jamais qu'un changement est appliqué avant le
  résultat de l'outil.
- Si l'outil répond que l'approbation est « en attente », dis simplement que la
  proposition attend la confirmation de l'athlète (depuis la page ou la notification).
- Pas de shell libre : seuls les scripts du projet listés par la politique sont exécutables.
- Réponses concises, adaptées à un écran de téléphone.
"""


class BackendError(RuntimeError):
    """Erreur attendue d'un backend : message français lisible, pas de trace."""


@dataclass
class TurnContext:
    """Ce que le service fournit à un backend pour UN tour de conversation.

    `emit` et `request_approval` sont thread-safe. `request_approval` bloque
    jusqu'à la décision de l'athlète, l'expiration du délai d'attente en ligne
    (→ "pending", la proposition reste ouverte et reprendra la session plus
    tard), ou l'annulation du tour (→ "deny").
    """

    session_id: str
    workspace: Path
    config: dict                                   # section [chat] résolue
    emit: Callable[[str, dict], None]              # emit(type, payload)
    decide: Callable[[str, dict], str]             # politique : "allow" | "ask" | "deny"
    request_approval: Callable[[str, dict, str, list], Decision]  # (tool, input, summary, diff)
    cancelled: threading.Event = field(default_factory=threading.Event)
    # État propre au backend, persisté avec la session (ex. id de session SDK / OpenCode).
    backend_state: dict = field(default_factory=dict)
    language: str = "fr"


class ChatBackend(ABC):
    """Un backend traduit un harnais (SDK, serveur OpenCode, mock) vers le protocole."""

    name: str = "abstract"

    def __init__(self, workspace: Path, config: dict):
        self.workspace = workspace
        self.config = config

    @abstractmethod
    def run_turn(self, ctx: TurnContext, user_message: str) -> None:
        """Exécute un tour complet ; émet les événements ; se termine par `done`.

        Doit passer CHAQUE appel d'outil par `ctx.decide(tool, input)` puis, si
        "ask", par `ctx.request_approval(...)`. "deny" / "pending" → l'outil
        n'est pas exécuté et le modèle reçoit un refus explicite. Lève
        `BackendError` pour une erreur attendue (clé absente, fournisseur
        injoignable, crédit épuisé…).
        """

    def check(self) -> tuple:
        """(ok, message) sans dépenser de jetons — utilisé par /healthz et coach-doctor."""
        return True, f"backend {self.name}"

    def shutdown(self) -> None:
        """Libère les ressources (processus enfant, boucle asyncio…)."""


def load_backend(name: str, workspace: Path, config: dict) -> ChatBackend:
    """Fabrique : import paresseux, pour que `mock` n'exige aucun paquet tiers."""
    if name == "mock":
        from arc_chat_mock import MockBackend  # type: ignore
        return MockBackend(workspace, config)
    if name == "claude":
        from arc_chat_claude import ClaudeBackend  # type: ignore
        return ClaudeBackend(workspace, config)
    if name == "opencode":
        from arc_chat_opencode import OpenCodeBackend  # type: ignore
        return OpenCodeBackend(workspace, config)
    raise BackendError(f"Backend de chat inconnu : {name!r} (mock | claude | opencode)")


def resolve_workspace_path(workspace: Path, raw: Optional[str]) -> Optional[str]:
    """Chemin relatif au workspace, ou None s'il en sort (défense contre `..`)."""
    if not raw:
        return None
    try:
        p = (workspace / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        return p.relative_to(workspace.resolve()).as_posix()
    except (ValueError, OSError):
        return None
