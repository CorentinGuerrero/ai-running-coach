#!/usr/bin/env python3
"""Backend « claude » du chat coach : Claude Agent SDK (paquet `claude-agent-sdk`).

Le SDK EST le harnais Claude Code en bibliothèque : il charge `.claude/agents`,
skills, `.mcp.json` et `AGENTS.md` du workspace comme l'IDE. Authentification par
clé API uniquement (variable nommée par `[chat].api_key_env`), jamais l'OAuth
d'un abonnement.

Sources officielles vérifiées (claude-agent-sdk 0.2.161, CLI embarqué 2.1.284) :
  - https://code.claude.com/docs/en/agent-sdk/python      (ClaudeAgentOptions, messages)
  - https://code.claude.com/docs/en/agent-sdk/permissions (ordre d'évaluation, can_use_tool, hooks)
  - https://github.com/anthropics/claude-agent-sdk-python (le wheel EMBARQUE le CLI Claude Code :
    pas de Node à installer ; Python >= 3.10) et le code du wheel lui-même (types.py, client.py).

Faits établis dans le code du wheel :
  - `can_use_tool` : `async (tool_name, input, ToolPermissionContext) -> PermissionResultAllow|Deny`,
    `ToolPermissionContext.tool_use_id` toujours renseigné ; il n'est appelé QUE pour les appels
    qui ne sont pas déjà approuvés (règles allow, lectures dans le cwd, `acceptEdits`…).
  - Pour que CHAQUE appel passe par la politique, on branche donc AUSSI un hook `PreToolUse`
    (`HookMatcher`), exécuté avant tout le reste ; les deux partagent un cache par `tool_use_id`
    pour ne jamais demander deux fois la même approbation.
  - `ClaudeSDKClient` (mode streaming) : `connect()`, `query()`, `receive_response()`,
    `interrupt()`, `disconnect()`. `StreamEvent.event` = évènement brut de l'API Messages.
  - `ResultMessage` : `subtype`, `is_error`, `session_id`, `total_cost_usd`, `usage`.
  - `system_prompt={"type": "preset", "preset": "claude_code", "append": ...}`.

Le module s'importe sans le paquet : `claude_agent_sdk` n'est importé que dans les méthodes.
"""

from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import Any, Optional

from arc_chat_backend import (SYSTEM_ADDENDUM, BackendError, ChatBackend, TurnContext,
                              resolve_workspace_path)
from arc_chat_tools import (REFUSAL_DENY, display_input, gate, short, summarize_tool,
                            usd_to_eur)

SDK_TESTED_VERSION = "0.2.161"
DEFAULT_API_KEY_ENV = "ANTHROPIC_API_KEY"

# Outils natifs retirés du contexte du modèle (interaction terminal sans objet dans le chat).
DISALLOWED_TOOLS = ["AskUserQuestion", "TodoWrite", "EnterPlanMode", "ExitPlanMode"]

_FS_WRITE = ("Write", "Edit", "MultiEdit", "NotebookEdit")
_FS_LIST = ("Glob", "Grep", "LS")
_LEANPROXY_META = ("list_servers", "list_tools", "search_tools")


def canonical_tool(name: str, tool_input: Optional[dict]) -> tuple:
    """Nom d'outil Claude Code -> (nom canonique, entrée canonique)."""
    inp = dict(tool_input or {})
    if name in ("Read", "NotebookRead"):
        return "fs.read", {"path": inp.get("file_path") or inp.get("notebook_path") or ""}
    if name in _FS_WRITE:
        out = {k: v for k, v in inp.items() if k not in ("file_path", "notebook_path")}
        out["path"] = inp.get("file_path") or inp.get("notebook_path") or ""
        return "fs.write", out
    if name in _FS_LIST:
        out = {"path": inp.get("path") or "."}
        if inp.get("pattern"):
            out["pattern"] = inp["pattern"]
        return "fs.list", out
    if name == "Bash":
        return "shell", {"command": inp.get("command", "")}
    if name == "WebFetch":
        return "web.fetch", {"url": inp.get("url", "")}
    if name == "WebSearch":
        return "web.search", {"query": inp.get("query", "")}
    if name in ("Task", "Agent"):
        return "task", {"agent": inp.get("subagent_type") or inp.get("agent") or ""}
    if name == "Skill":
        return "skill", {"name": inp.get("skill") or inp.get("name") or ""}
    if name.startswith("mcp__"):
        parts = name.split("__", 2)
        server = parts[1].lower() if len(parts) > 1 else ""
        tool = parts[2] if len(parts) > 2 else ""
        # Passerelle leanproxy : leanproxy_invoke_tool(server=…, tool=…, arguments={…}).
        if server.startswith("leanproxy") and tool.endswith("invoke_tool") and inp.get("server") \
                and inp.get("tool"):
            args = inp.get("arguments")
            if args is None:
                args = inp.get("args")
            return f"mcp:{str(inp['server']).lower()}.{inp['tool']}", dict(args or {})
        if server.startswith("leanproxy") and tool in _LEANPROXY_META:
            return f"mcp:{server}.{tool}", inp
        return f"mcp:{server}.{tool}", inp
    return f"other:{name}", inp


class _Turn:
    """État d'UN tour : contexte, cache d'approbations, outils en vol."""

    def __init__(self, ctx: TurnContext, workspace: Path):
        self.ctx = ctx
        self.workspace = workspace
        self.cache: dict = {}            # tool_use_id -> (décision, message)
        self.cache_lock = threading.Lock()
        self.tools: dict = {}            # tool_use_id -> (canonique, entrée)
        self.pending = False
        self.streamed_text = False
        self.usage_emitted = False

    def gate_sync(self, tool_use_id: Optional[str], name: str, tool_input: dict) -> tuple:
        """Politique + approbation (bloquant, exécuté dans un thread)."""
        if tool_use_id:
            with self.cache_lock:
                hit = self.cache.get(tool_use_id)
            if hit is not None:
                return hit
        tool, cinput = canonical_tool(name, tool_input)
        result = gate(self.ctx, tool, cinput)
        if result[0] == "pending":
            self.pending = True
        if tool_use_id:
            with self.cache_lock:
                self.cache[tool_use_id] = result
        return result


class ClaudeBackend(ChatBackend):
    name = "claude"

    def __init__(self, workspace: Path, config: dict):
        super().__init__(workspace, config)

    # -- configuration -------------------------------------------------

    def _api_key_env(self) -> str:
        return str(self.config.get("api_key_env") or DEFAULT_API_KEY_ENV)

    def _api_key(self) -> str:
        return os.environ.get(self._api_key_env(), "").strip()

    def check(self) -> tuple:
        try:
            import claude_agent_sdk  # type: ignore
        except ImportError:
            return False, "paquet claude-agent-sdk absent — pip install claude-agent-sdk"
        if not self._api_key():
            return False, (f"clé API absente : variable {self._api_key_env()} vide "
                           "(à renseigner dans ~/.config/ai-running-coach/llm.env)")
        version = getattr(claude_agent_sdk, "__version__", "?")
        return True, f"claude-agent-sdk {version} (testé avec {SDK_TESTED_VERSION})"

    def _options(self, sdk: Any, turn: _Turn, resume: Optional[str]) -> Any:
        cfg = self.config
        key = self._api_key()
        env = {
            "ANTHROPIC_API_KEY": key,
            # Jamais d'abonnement : on neutralise les autres sources d'identifiants.
            # À VÉRIFIER : la chaîne vide est bien traitée comme « non définie » par le CLI.
            "CLAUDE_CODE_OAUTH_TOKEN": "",
            "ANTHROPIC_AUTH_TOKEN": "",
        }

        async def pre_tool_use(input_data: dict, tool_use_id: Optional[str], _context: Any) -> dict:
            name = input_data.get("tool_name", "")
            tuid = tool_use_id or input_data.get("tool_use_id")
            decision, message = await asyncio.to_thread(
                turn.gate_sync, tuid, name, input_data.get("tool_input") or {})
            out = {"hookEventName": "PreToolUse",
                   "permissionDecision": "allow" if decision == "allow" else "deny"}
            if decision != "allow":
                out["permissionDecisionReason"] = message
            return {"hookSpecificOutput": out}

        async def can_use_tool(name: str, tool_input: dict, context: Any) -> Any:
            decision, message = await asyncio.to_thread(
                turn.gate_sync, getattr(context, "tool_use_id", None), name, tool_input)
            if decision == "allow":
                return sdk.PermissionResultAllow()
            return sdk.PermissionResultDeny(message=message or REFUSAL_DENY)

        kwargs: dict = dict(
            cwd=str(self.workspace),
            setting_sources=["project"],
            system_prompt={"type": "preset", "preset": "claude_code", "append": SYSTEM_ADDENDUM},
            can_use_tool=can_use_tool,
            hooks={"PreToolUse": [sdk.HookMatcher(matcher=None, hooks=[pre_tool_use])]},
            include_partial_messages=True,
            permission_mode="default",
            disallowed_tools=list(DISALLOWED_TOOLS),
            env=env,
        )
        if cfg.get("model"):
            kwargs["model"] = str(cfg["model"])
        if cfg.get("max_turns"):
            kwargs["max_turns"] = int(cfg["max_turns"])
        if resume:
            kwargs["resume"] = resume
        return sdk.ClaudeAgentOptions(**kwargs)

    # -- tour ------------------------------------------------------------

    def run_turn(self, ctx: TurnContext, user_message: str) -> None:
        try:
            import claude_agent_sdk as sdk  # type: ignore
        except ImportError:
            raise BackendError("Le paquet claude-agent-sdk n'est pas installé "
                               "(pip install claude-agent-sdk).")
        if not self._api_key():
            raise BackendError(f"Clé API Anthropic absente : la variable {self._api_key_env()} "
                               "est vide (voir ~/.config/ai-running-coach/llm.env).")
        turn = _Turn(ctx, self.workspace)
        try:
            # Boucle privée par tour : le service appelle run_turn depuis un thread.
            asyncio.run(self._run_async(sdk, turn, user_message))
        except BackendError:
            raise
        except Exception as exc:  # noqa: BLE001 — traduit en message lisible
            raise BackendError(self._translate_exception(sdk, exc)) from exc

    @staticmethod
    def _translate_exception(sdk: Any, exc: Exception) -> str:
        if isinstance(exc, getattr(sdk, "CLINotFoundError", ())):
            return "Le CLI Claude Code est introuvable (réinstaller claude-agent-sdk)."
        text = str(exc)
        low = text.lower()
        if "401" in low or "authentication" in low or "invalid x-api-key" in low:
            return "Clé API Anthropic refusée (401) : vérifier la clé dans llm.env."
        if "402" in low or "credit balance" in low:
            return "Crédit Anthropic insuffisant (402)."
        return f"Erreur du backend Claude : {short(text, 200)}"

    async def _run_async(self, sdk: Any, turn: _Turn, user_message: str) -> None:
        ctx = turn.ctx
        resume = ctx.backend_state.get("sdk_session_id")
        options = self._options(sdk, turn, resume)
        client = sdk.ClaudeSDKClient(options=options)
        watcher: Optional[asyncio.Task] = None
        result: Any = None
        assistant_error: Optional[str] = None
        await client.connect()
        try:
            async def watch_cancel() -> None:
                while True:
                    await asyncio.sleep(0.1)
                    if ctx.cancelled.is_set():
                        try:
                            await client.interrupt()
                        except Exception:  # noqa: BLE001
                            pass
                        return

            watcher = asyncio.create_task(watch_cancel())
            await client.query(user_message)
            async for message in client.receive_response():
                kind = type(message).__name__
                sid = getattr(message, "session_id", None)
                if sid and kind in ("ResultMessage", "StreamEvent", "SystemMessage"):
                    ctx.backend_state["sdk_session_id"] = sid
                if kind == "StreamEvent":
                    self._on_stream_event(turn, message)
                elif kind == "AssistantMessage":
                    assistant_error = getattr(message, "error", None) or assistant_error
                    self._on_assistant(turn, message)
                elif kind == "UserMessage":
                    self._on_user(turn, message)
                elif kind == "ResultMessage":
                    result = message
        finally:
            if watcher:
                watcher.cancel()
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        self._finish(turn, result, assistant_error)

    # -- traduction des messages ---------------------------------------

    def _on_stream_event(self, turn: _Turn, message: Any) -> None:
        if getattr(message, "parent_tool_use_id", None):
            return  # texte interne d'un sous-agent : non affiché
        event = getattr(message, "event", None) or {}
        if event.get("type") == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta" and delta.get("text"):
                turn.streamed_text = True
                turn.ctx.emit("text_delta", {"text": delta["text"]})

    def _on_assistant(self, turn: _Turn, message: Any) -> None:
        top_level = not getattr(message, "parent_tool_use_id", None)
        for block in getattr(message, "content", None) or []:
            bname = type(block).__name__
            if bname == "TextBlock" and top_level and not turn.streamed_text and block.text:
                turn.ctx.emit("text_delta", {"text": block.text})
            elif bname == "ToolUseBlock":
                tool, cinput = canonical_tool(block.name, block.input)
                turn.tools[block.id] = (tool, cinput)
                turn.ctx.emit("tool_start", {"id": block.id, "name": tool,
                                             "summary": summarize_tool(
                                                 tool, display_input(self.workspace, tool, cinput))})
        if top_level:
            turn.streamed_text = False

    def _on_user(self, turn: _Turn, message: Any) -> None:
        content = getattr(message, "content", None)
        if not isinstance(content, list):
            return
        for block in content:
            if type(block).__name__ != "ToolResultBlock":
                continue
            tool, cinput = turn.tools.get(block.tool_use_id, ("other:inconnu", {}))
            ok = not bool(block.is_error)
            cached = turn.cache.get(block.tool_use_id)
            if not ok and cached and cached[0] != "allow":
                summary = "Refusé" if cached[0] == "deny" else "En attente de confirmation"
            else:
                summary = "Terminé" if ok else "Échec"
            turn.ctx.emit("tool_end", {"id": block.tool_use_id, "ok": ok, "summary": summary})
            if ok and tool == "fs.write":
                rel = resolve_workspace_path(self.workspace, cinput.get("path"))
                if rel:
                    turn.ctx.emit("file_written", {"path": rel})

    def _finish(self, turn: _Turn, result: Any, assistant_error: Optional[str]) -> None:
        ctx = turn.ctx
        if result is not None:
            usage = getattr(result, "usage", None) or {}
            ctx.emit("usage", {
                "input_tokens": int(usage.get("input_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or 0),
                "cache_read_tokens": int(usage.get("cache_read_input_tokens") or 0),
                "cost_eur": usd_to_eur(getattr(result, "total_cost_usd", None),
                                       self.config.get("usd_eur_rate")),
            })
        if assistant_error == "authentication_failed":
            raise BackendError("Clé API Anthropic refusée (401) : vérifier la clé dans llm.env.")
        if assistant_error == "billing_error":
            raise BackendError("Crédit Anthropic insuffisant (402).")
        if assistant_error == "rate_limit":
            raise BackendError("Limite de débit Anthropic atteinte : réessaie dans un instant.")
        subtype = getattr(result, "subtype", "") if result is not None else ""
        if result is not None and getattr(result, "is_error", False) and subtype != "error_max_turns":
            detail = short(getattr(result, "result", None) or subtype or "erreur inconnue", 200)
            raise BackendError(f"Le backend Claude a échoué : {detail}")
        if ctx.cancelled.is_set():
            reason = "interrupted"
        elif turn.pending:
            reason = "pending_approval"
        elif subtype == "error_max_turns":
            reason = "max_turns"
        else:
            reason = "end_turn"
        ctx.emit("done", {"reason": reason})

    def shutdown(self) -> None:
        """Rien à libérer : une boucle asyncio et un client par tour, fermés en fin de tour."""
