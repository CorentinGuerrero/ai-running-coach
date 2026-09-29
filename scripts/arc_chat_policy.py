#!/usr/bin/env python3
"""Politique de permissions du chat coach : « allow », « ask » ou « deny ».

Une seule politique pour tous les backends (deploy/chat/SPEC.md, « Policy »).
Les noms d'outils sont canoniques (`scripts/arc_chat_backend.py`) ; les règles
viennent de `config/chat-policy.toml` (versionné, sans secret). Ce qui n'est
pas explicitement permis est refusé.

    Policy.load(racine_ou_fichier, workspace).decide("fs.write", {"path": "planning/x.md"})

Bibliothèque standard uniquement (CONTRIBUTING.md).
"""

from __future__ import annotations

import fnmatch
import re
import shlex
import sys
from pathlib import Path
from typing import Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_chat_backend import payload_hash, resolve_workspace_path  # noqa: E402
from coach_config import read_toml  # noqa: E402

POLICY_FILE = "config/chat-policy.toml"

# Métacaractères shell interdits dans une commande autorisée.
SHELL_META = set(";|&$`><()\n\r")

# Valeurs de repli si le fichier est absent ou incomplet : elles reproduisent
# `config/chat-policy.toml` (le refus reste le comportement par défaut).
DEFAULTS = {
    "fs": {
        "write_dirs": ["activities", "medical", "nutrition", "planning", "rapports"],
        "secret_patterns": ["workspace.user.toml", ".env", "*.env", "*.token", ".garminconnect",
                            "llm.env", "*.pem", "*.key"],
    },
    "shell": {"allowed_prefixes": ["python3 scripts/arc_index.py", "python3 scripts/arc_log.py"]},
    "web": {"fetch_domains": ["wttr.in", "overpass-api.de", "nominatim.openstreetmap.org"]},
    "mcp": {
        "servers": ["garmin", "intervals"],
        "read_prefixes": ["get_", "count_", "list_", "download_"],
        "write_tools": ["schedule_*", "delete_*", "upload_*", "create_*", "add_*", "set_*", "log_*",
                        "update_*", "remove_*", "request_reload"],
    },
}


def _as_list(value) -> list:
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else []


class Policy:
    """Règles chargées ; `decide` est pur (aucun effet de bord, thread-safe)."""

    def __init__(self, workspace: Path, rules: Optional[dict] = None):
        self.workspace = Path(workspace).resolve()
        merged = {section: dict(values) for section, values in DEFAULTS.items()}
        for section, values in (rules or {}).items():
            if isinstance(values, dict):
                merged.setdefault(section, {}).update(values)
        self.write_dirs = _as_list(merged["fs"].get("write_dirs"))
        self.secret_patterns = _as_list(merged["fs"].get("secret_patterns"))
        self.shell_prefixes = _as_list(merged["shell"].get("allowed_prefixes"))
        self.fetch_domains = [d.lower() for d in _as_list(merged["web"].get("fetch_domains"))]
        self.mcp_servers = [s.lower() for s in _as_list(merged["mcp"].get("servers"))]
        self.mcp_read_prefixes = _as_list(merged["mcp"].get("read_prefixes"))
        self.mcp_write_tools = _as_list(merged["mcp"].get("write_tools"))

    @classmethod
    def load(cls, repo_root_or_path, workspace) -> "Policy":
        """`repo_root_or_path` : racine du dépôt (on lit `config/chat-policy.toml`) ou fichier TOML.

        Sans fichier à cet endroit, celui du workspace est tenté, puis les défauts ci-dessus.
        """
        given = Path(repo_root_or_path)
        first = given if given.is_file() else given / POLICY_FILE
        for path in (first, Path(workspace) / POLICY_FILE):
            if path.is_file():
                return cls(Path(workspace), read_toml(path))
        return cls(Path(workspace), {})

    # -- décisions -----------------------------------------------------------

    def decide(self, tool: str, tool_input: dict, preapproved: Iterable[str] = ()) -> str:
        """« allow » | « ask » | « deny ». Un hash pré-approuvé ne lève que « ask », jamais « deny »."""
        tool_input = tool_input if isinstance(tool_input, dict) else {}
        verdict = self._base(tool, tool_input)
        if verdict == "ask" and preapproved and payload_hash(tool, tool_input) in set(preapproved):
            return "allow"
        return verdict

    def _base(self, tool: str, tool_input: dict) -> str:
        if tool in ("fs.read", "fs.list"):
            return self._fs_read(tool_input)
        if tool == "fs.write":
            return self._fs_write(tool_input)
        if tool == "shell":
            return self._shell(str(tool_input.get("command") or ""))
        if tool == "web.fetch":
            return self._web_fetch(str(tool_input.get("url") or ""))
        if tool in ("task", "skill"):
            return "allow"
        if tool.startswith("mcp:"):
            return self._mcp(tool)
        return "deny"           # web.search, other:*, inconnu

    def _secret(self, rel: str) -> bool:
        parts = [p for p in rel.split("/") if p]
        return any(fnmatch.fnmatch(part, pattern) for part in parts for pattern in self.secret_patterns)

    def _fs_read(self, tool_input: dict) -> str:
        raw = tool_input.get("path")
        if raw in (None, "", "."):
            return "allow"                       # racine du workspace (ls, glob)
        rel = resolve_workspace_path(self.workspace, str(raw))
        if rel is None or self._secret(rel):
            return "deny"
        if rel == ".arc" or rel.startswith(".arc/"):
            return "deny"                        # index, sessions, approbations : jamais via le modèle
        return "allow"

    def _fs_write(self, tool_input: dict) -> str:
        rel = resolve_workspace_path(self.workspace, str(tool_input.get("path") or ""))
        if rel is None or self._secret(rel) or "/" not in rel:
            return "deny"
        return "allow" if rel.split("/", 1)[0] in self.write_dirs else "deny"

    def _shell(self, command: str) -> str:
        command = command.strip()
        if not command or any(ch in SHELL_META for ch in command):
            return "deny"
        try:
            words = shlex.split(command)
        except ValueError:
            return "deny"
        normalized = " ".join(words)
        for prefix in self.shell_prefixes:
            if normalized == prefix or normalized.startswith(prefix + " "):
                # Pas de remontée de répertoire dans les arguments.
                return "deny" if any(".." in w.split("/") for w in words) else "allow"
        return "deny"

    def _web_fetch(self, url: str) -> str:
        match = re.match(r"^https?://([^/:?#@\s]+)(?::\d+)?(?:[/?#]|$)", url, re.I)
        if not match:
            return "deny"
        host = match.group(1).lower()
        return "allow" if any(host == d or host.endswith("." + d) for d in self.fetch_domains) else "deny"

    def _mcp(self, tool: str) -> str:
        server, _, name = tool[len("mcp:"):].partition(".")
        if server.lower() not in self.mcp_servers or not name:
            return "deny"
        if any(fnmatch.fnmatch(name, pattern) for pattern in self.mcp_write_tools):
            return "ask"
        if any(name.startswith(prefix) for prefix in self.mcp_read_prefixes):
            return "allow"
        return "ask"            # outil inconnu d'un serveur connu : dans le doute, l'athlète tranche
