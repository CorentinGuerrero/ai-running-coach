#!/usr/bin/env python3
"""Briques communes aux backends du chat coach (Claude, OpenCode).

Résumés français courts, diff d'approbation, textes de refus renvoyés au modèle,
conversion USD -> EUR. Aucune dépendance : bibliothèque standard uniquement.
Fichier propre à l'agent « backends » (pas listé dans SPEC, ajouté pour éviter
de dupliquer ce code dans les deux adaptateurs).
"""

from __future__ import annotations

import json
from typing import Any

# Texte renvoyé au modèle quand l'outil n'est pas exécuté.
REFUSAL_DENY = ("Refusé : cette action n'est pas autorisée par la politique du coach "
                "ou l'athlète l'a refusée. Ne la réessaie pas ; explique-le simplement à l'athlète.")
REFUSAL_PENDING = "La proposition attend la confirmation de l'athlète."

MAX_DIFF_LINES = 40
MAX_TEXT = 80


def short(text: Any, limit: int = MAX_TEXT) -> str:
    """Texte sur une ligne, tronqué."""
    s = " ".join(str(text if text is not None else "").split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def usd_to_eur(usd: Any, rate: Any) -> float:
    """USD -> EUR arrondi au millionième d'euro ; 0 si la valeur est absente."""
    try:
        r = float(rate) if rate else 0.92
        return round(float(usd or 0.0) * r, 6)
    except (TypeError, ValueError):
        return 0.0


def _server_label(server: str) -> str:
    return {"garmin": "Garmin", "intervals": "intervals.icu"}.get(server, server)


def display_input(workspace: Any, tool: str, tool_input: dict) -> dict:
    """Copie d'affichage : chemins du workspace rendus relatifs (résumés courts pour l'athlète)."""
    inp = dict(tool_input or {})
    raw = inp.get("path")
    if tool.startswith("fs.") and raw and workspace is not None:
        try:
            from pathlib import Path
            p = Path(str(raw))
            if p.is_absolute():
                inp["path"] = p.resolve().relative_to(Path(workspace).resolve()).as_posix()
        except (ValueError, OSError):
            pass
    return inp


def summarize_tool(tool: str, tool_input: dict) -> str:
    """Résumé français d'un appel d'outil canonique (pas de valeurs de santé)."""
    inp = tool_input or {}
    if tool == "fs.read":
        return f"Lecture de {short(inp.get('path'))}"
    if tool == "fs.write":
        return f"Écriture de {short(inp.get('path'))}"
    if tool == "fs.list":
        return f"Recherche dans {short(inp.get('path') or '.')}"
    if tool == "shell":
        return f"Commande : {short(inp.get('command'), 60)}"
    if tool == "web.fetch":
        return f"Consultation de {short(inp.get('url'), 60)}"
    if tool == "web.search":
        return f"Recherche web : {short(inp.get('query'), 60)}"
    if tool == "task":
        return f"Délégation à l'agent {short(inp.get('agent') or '?')}"
    if tool == "skill":
        return f"Chargement de la compétence {short(inp.get('name') or '?')}"
    if tool.startswith("mcp:"):
        server, _, name = tool[4:].partition(".")
        return f"{_server_label(server)} : {name}"
    return f"Outil {short(tool)}"


def approval_diff(tool: str, tool_input: dict) -> list:
    """Diff lisible pour la carte d'approbation : [{"op": "+"|"-"|" ", "text": str}]."""
    inp = tool_input or {}
    out: list = []
    if tool == "fs.write":
        old, new = inp.get("old_string") or inp.get("oldString"), inp.get("new_string") or inp.get("newString")
        if old or new:
            out += [{"op": "-", "text": line} for line in str(old or "").splitlines()]
            out += [{"op": "+", "text": line} for line in str(new or "").splitlines()]
        elif inp.get("content") is not None:
            out += [{"op": "+", "text": line} for line in str(inp["content"]).splitlines()]
        else:
            out.append({"op": " ", "text": short(inp.get("path"))})
    else:
        try:
            dumped = json.dumps(inp, ensure_ascii=False, indent=2, sort_keys=True)
        except (TypeError, ValueError):
            dumped = str(inp)
        out += [{"op": "+", "text": line} for line in dumped.splitlines()]
    if len(out) > MAX_DIFF_LINES:
        rest = len(out) - MAX_DIFF_LINES
        out = out[:MAX_DIFF_LINES] + [{"op": " ", "text": f"… ({rest} lignes de plus)"}]
    return out


def parse_unified_diff(diff_text: str) -> list:
    """Convertit un diff unifié (OpenCode `metadata.diff`) en lignes d'approbation."""
    out: list = []
    for line in (diff_text or "").splitlines():
        if line.startswith(("Index:", "====", "---", "+++", "@@")):
            continue
        if line[:1] in ("+", "-"):
            out.append({"op": line[0], "text": line[1:]})
        elif line.startswith(" "):
            out.append({"op": " ", "text": line[1:]})
    if len(out) > MAX_DIFF_LINES:
        rest = len(out) - MAX_DIFF_LINES
        out = out[:MAX_DIFF_LINES] + [{"op": " ", "text": f"… ({rest} lignes de plus)"}]
    return out


def gate(ctx: Any, tool: str, tool_input: dict, diff: Any = None) -> tuple:
    """Politique puis approbation : renvoie (« allow » | « deny » | « pending », texte de refus).

    Implémentation unique pour les deux backends : `ctx.decide` d'abord ; sur
    « ask », `ctx.request_approval` (bloquant). Toute réponse inattendue vaut refus.
    """
    decision = ctx.decide(tool, tool_input)
    if decision == "allow":
        return "allow", ""
    if decision != "ask":
        return "deny", REFUSAL_DENY
    result = ctx.request_approval(tool, tool_input, summarize_tool(tool, tool_input),
                                  diff if diff is not None else approval_diff(tool, tool_input))
    if result == "allow":
        return "allow", ""
    if result == "pending":
        return "pending", REFUSAL_PENDING
    return "deny", REFUSAL_DENY
