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
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_chat_backend import payload_hash, resolve_workspace_path  # noqa: E402
from coach_config import read_toml  # noqa: E402

POLICY_FILE = "config/chat-policy.toml"

# Métacaractères shell interdits dans une commande autorisée : redirections, chaînage,
# substitutions, échappement (`\` ferait diverger shlex et le vrai shell), `~` (expansion
# du répertoire personnel), jokers et accolades (un joker contournerait la liste des secrets).
SHELL_META = set(";|&$`><()\n\r\\~*?[]{}!#")

# Un argument qui se termine ainsi est traité comme un chemin même sans « / ».
PATH_SUFFIXES = (".md", ".json", ".jsonl", ".toml", ".db", ".sqlite", ".gpx", ".fit", ".csv", ".txt",
                 ".yml", ".yaml", ".env", ".token", ".pem", ".key", ".py", ".sh")

# Options toujours permises (sans valeur) pour tout script de la liste blanche.
COMMON_FLAGS = ("--help", "-h")

# Borne de l'expansion réelle d'un joker (fs.list) : au-delà, on refuse.
GLOB_SCAN_LIMIT = 20000

WILDCARDS = "*?["

# Bornes de l'expansion d'accolades d'un glob (fs.list) : au-delà, refus (jamais de troncature).
BRACE_MAX_EXPANSION = 64
BRACE_MAX_DEPTH = 3

# Valeurs de repli si le fichier est absent ou incomplet : elles reproduisent
# `config/chat-policy.toml` (le refus reste le comportement par défaut).
DEFAULTS = {
    "fs": {
        "write_dirs": ["activities", "medical", "nutrition", "planning", "rapports"],
        "secret_patterns": ["workspace.user.toml", ".env", "*.env", "*.token", ".garminconnect",
                            "llm.env", "*.pem", "*.key"],
        # Dossiers où une recherche de contenu (grep, `pattern`) est permise, en plus de write_dirs.
        "search_dirs": ["resources", "skills", "agents", "templates", "docs"],
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

# Options des scripts de repli (aucun fichier de politique) : les deux premiers scripts seulement.
DEFAULT_SCRIPTS = {
    "scripts/arc_index.py": {
        "flags": ["--memory", "--rebuild", "--with-gps", "--assumptions", "--calibration", "--active"],
        "value_options": ["--today", "--activity", "--weeks", "--segment", "--date", "--days", "--since",
                          "--limit", "--trigger", "--outcome", "--months", "--band"],
        "read_options": ["--validate"],
        "multi_value_options": ["--validate"],
        "output_options": ["--db"],
    },
    "scripts/arc_log.py": {
        "read_options": ["--input"],
        "output_options": ["--output"],
    },
}


def _as_list(value) -> list:
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else []


def _script_rules(rules: dict) -> dict:
    """Options permises par script : `[shell.scripts."scripts/x.py"]` → {script: {clé: [options]}}.

    Deux formes selon le lecteur TOML : tableaux imbriqués (tomllib) ou nom de section
    complet en clé (repli Python < 3.11, qui n'imbrique pas).
    """
    found: dict = {}
    shell = rules.get("shell")
    nested = shell.get("scripts") if isinstance(shell, dict) else None
    if isinstance(nested, dict):
        for script, table in nested.items():
            if isinstance(table, dict):
                found[str(script)] = {k: _as_list(v) for k, v in table.items()}
    for key, table in rules.items():
        match = re.match(r'^shell\.scripts\.["\']?(.+?)["\']?$', str(key))
        if match and isinstance(table, dict):
            found[match.group(1)] = {k: _as_list(v) for k, v in table.items()}
    return found


def _has_wildcard(text: str) -> bool:
    return any(ch in text for ch in WILDCARDS)


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
        self.search_dirs = _as_list(merged["fs"].get("search_dirs")) + list(self.write_dirs)
        self.shell_prefixes = _as_list(merged["shell"].get("allowed_prefixes"))
        self.shell_scripts = _script_rules(rules or {}) or {k: dict(v) for k, v in DEFAULT_SCRIPTS.items()}
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
        if tool == "fs.read":
            return self._fs_read(tool_input)
        if tool == "fs.list":
            return self._fs_list(tool_input)
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
        # Comparaison insensible à la casse des deux côtés (macOS : `.ARC` et `.arc` sont le même dossier).
        parts = [p.casefold() for p in rel.split("/") if p]
        return any(fnmatch.fnmatchcase(part, pattern.casefold())
                   for part in parts for pattern in self.secret_patterns)

    @staticmethod
    def _in_arc(rel: str) -> bool:
        low = rel.casefold()
        return low == ".arc" or low.startswith(".arc/")

    def _fs_read(self, tool_input: dict) -> str:
        raw = tool_input.get("path")
        if raw in (None, "", "."):
            return "allow"                       # racine du workspace (ls, glob)
        rel = resolve_workspace_path(self.workspace, str(raw))
        if rel is None or self._secret(rel):
            return "deny"
        if self._in_arc(rel):
            return "deny"                        # index, sessions, approbations : jamais via le modèle
        return "allow"

    def _fs_write(self, tool_input: dict) -> str:
        rel = resolve_workspace_path(self.workspace, str(tool_input.get("path") or ""))
        if rel is None or self._secret(rel) or "/" not in rel:
            return "deny"
        return "allow" if rel.split("/", 1)[0] in self.write_dirs else "deny"

    # -- fs.list : filtres de fichiers (glob) ----------------------------------------

    @staticmethod
    def _expand_braces(glob: str) -> Optional[list]:
        """`*.{md,toml}` → [`*.md`, `*.toml`] ; None si l'expansion dépasse la borne ou si
        l'imbrication dépasse le maximum : l'appelant refuse (jamais de troncature silencieuse)."""
        depth = level = 0
        for ch in glob:
            if ch == "{":
                level += 1
                depth = max(depth, level)
            elif ch == "}":
                level = max(0, level - 1)
        if depth > BRACE_MAX_DEPTH:
            return None
        out = [glob]
        while True:
            nxt: list = []
            changed = False
            for item in out:
                match = re.search(r"\{([^{}]*)\}", item)
                if not match:
                    nxt.append(item)
                    continue
                changed = True
                for alt in match.group(1).split(","):
                    nxt.append(item[:match.start()] + alt + item[match.end():])
                if len(nxt) > BRACE_MAX_EXPANSION:
                    return None
            out = nxt
            if len(out) > BRACE_MAX_EXPANSION:
                return None
            if not changed:
                return out

    def _component_may_match_secret(self, component: str) -> bool:
        """Un composant de glob peut-il désigner un secret ? Comparaison dans les deux sens."""
        if not component:
            return False
        comp = component.casefold()
        return any(fnmatch.fnmatchcase(pattern.casefold(), comp) or fnmatch.fnmatchcase(comp, pattern.casefold())
                   for pattern in self.secret_patterns)

    def _fs_list(self, tool_input: dict) -> str:
        """`path` comme fs.read, puis chaque valeur de `glob` (chaîne ou liste) ; `pattern` n'est pas un chemin."""
        if self._fs_read(tool_input) != "allow":
            return "deny"
        globs = tool_input.get("glob")
        globs = [globs] if isinstance(globs, str) else (list(globs) if isinstance(globs, (list, tuple)) else [])
        raw = tool_input.get("path")
        base = "" if raw in (None, "", ".") else (resolve_workspace_path(self.workspace, str(raw)) or "")
        if tool_input.get("pattern") and not self._search_dir_ok(base):
            return "deny"                                   # grep : le contenu des fichiers serait lu
        for glob in globs:
            if not isinstance(glob, str) or not glob.strip():
                continue
            expanded = self._expand_braces(glob.strip())
            if expanded is None:
                return "deny"
            for one in expanded:
                if not self._glob_ok(base, one):
                    return "deny"
        return "allow"

    def _search_dir_ok(self, base: str) -> bool:
        """Une recherche de contenu ne porte que sur un dossier de `[fs].search_dirs` (ou un sous-dossier)."""
        first = base.split("/", 1)[0] if base else ""
        return bool(first) and first in self.search_dirs

    def _glob_ok(self, base: str, glob: str) -> bool:
        if glob.startswith(("/", "~")) or "\\" in glob or ".." in glob.split("/"):
            return False
        parts = [p for p in glob.split("/") if p and p != "."]
        if not parts:
            return True
        if any(not _has_wildcard(p) and (self._secret(p) or self._in_arc(p)) for p in parts):
            return False                                    # nom de secret (ou `.arc`) cité tel quel
        if any(self._component_may_match_secret(p) for p in parts[-1:]) or any(
                not set(p) <= {"*"} and self._component_may_match_secret(p) for p in parts[:-1]):
            # Joker large ou proche d'un secret : toléré seulement dans un dossier de données
            # littéral (jamais config/, jamais la racine, jamais récursif), après vérification réelle.
            literal = [p for p in base.split("/") if p]
            for part in parts[:-1]:
                if _has_wildcard(part):
                    break
                literal.append(part)
            if not literal or literal[0] not in self.write_dirs or "**" in parts:
                return False
        return not self._glob_hits_secret(base, parts)

    def _glob_hits_secret(self, base: str, parts: list) -> bool:
        """Développe le glob sur le disque (borné) : vrai si un fichier réel est un secret ou sous `.arc/`."""
        joined = "/".join(parts)
        if not _has_wildcard(joined):
            rel = (base + "/" + joined).lstrip("/")
            return self._secret(rel) or self._in_arc(rel)
        root = (self.workspace / base) if base else self.workspace
        seen = 0
        try:
            for match in root.glob(joined):
                seen += 1
                if seen > GLOB_SCAN_LIMIT:
                    return True                             # trop large pour être vérifié
                rel = os.path.relpath(match, self.workspace).replace(os.sep, "/")
                if self._secret(rel) or self._in_arc(rel):
                    return True
        except (OSError, ValueError, NotImplementedError):
            return True
        return False

    # -- shell : liste blanche par script et par option -------------------------------

    def _shell(self, command: str) -> str:
        command = command.strip()
        if not command or any(ch in SHELL_META for ch in command):
            return "deny"
        try:
            words = shlex.split(command)
        except ValueError:
            return "deny"
        for prefix in self.shell_prefixes:
            head = prefix.split()
            if head and words[:len(head)] == head:
                return self._shell_args(head[-1], words[len(head):])
        return "deny"

    def _shell_args(self, script: str, args: list) -> str:
        """Chaque option doit être connue du script ; chaque chemin reste dans le workspace."""
        rules = self.shell_scripts.get(script, {})
        flags = set(rules.get("flags", [])) | set(COMMON_FLAGS)
        outputs = set(rules.get("output_options", []))
        reads = set(rules.get("read_options", []))
        valued = outputs | reads | set(rules.get("value_options", []))
        multi = set(rules.get("multi_value_options", []))   # nargs "*" / "+" : plusieurs valeurs à la suite
        i = 0
        while i < len(args):
            token = args[i]
            i += 1
            if self._option_like(token):
                name, eq, inline = token.partition("=")
                if name in flags and not eq:
                    continue
                if name not in valued:
                    return "deny"                           # option inconnue : refusée
                kind = "write" if name in outputs else "read" if name in reads else "plain"
                values: list = []
                if eq:
                    values = [inline]
                elif name in multi:
                    while i < len(args) and not self._option_like(args[i]):
                        values.append(args[i])
                        i += 1
                elif i < len(args):
                    values, i = [args[i]], i + 1
                else:
                    return "deny"
                # Jamais de valeur qui commence par « - » : argparse la lirait comme une autre option
                # (ou l'avalerait) et la politique ne verrait plus ce qui s'exécute vraiment.
                if any(v.startswith("-") for v in values):
                    return "deny"
            else:
                values, kind = [token], "plain"
            if not all(self._shell_value(v, kind) for v in values):
                return "deny"
        return "allow"

    @staticmethod
    def _option_like(token: str) -> bool:
        return token.startswith("-") and token != "-"

    def _shell_value(self, value: str, kind: str) -> bool:
        """Argument acceptable ? Les chemins restent dans le workspace, hors secrets et `.arc/`."""
        if value == "" and kind == "plain":
            return True
        for piece in [value] + ([value.partition("=")[2]] if "=" in value else []):
            if piece.startswith(("/", "~")) or Path(piece).is_absolute():
                return False
        segments = re.split(r"[/=]", value)
        if ".." in segments or any(self._secret(seg) for seg in segments if seg):
            return False
        pathlike = (kind != "plain" or "/" in value or value in (".", "..")
                    or value.lower().endswith(PATH_SUFFIXES))
        if not pathlike:
            return True
        rel = resolve_workspace_path(self.workspace, value)
        if rel is None or self._secret(rel) or self._in_arc(rel):
            return False
        if kind == "write":                                 # sortie : uniquement les dossiers de données
            return "/" in rel and rel.split("/", 1)[0] in self.write_dirs
        return True

    # -- web -------------------------------------------------------------------------

    def _web_fetch(self, url: str) -> str:
        """http(s) sans identifiants, sans encodage dans l'hôte, hôte ASCII, port par défaut, domaine listé."""
        if not url or url != url.strip() or "\\" in url or any(ord(c) <= 0x20 or ord(c) == 0x7F for c in url):
            return "deny"
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError:
            return "deny"
        if parts.scheme not in ("http", "https"):
            return "deny"
        netloc = parts.netloc
        if "@" in netloc or "%" in netloc or not netloc.isascii():
            return "deny"
        if port is not None and port != (443 if parts.scheme == "https" else 80):
            return "deny"
        host = (parts.hostname or "").lower()
        if not re.fullmatch(r"[a-z0-9]([a-z0-9.-]*[a-z0-9])?", host) or ".." in host:
            return "deny"
        return "allow" if any(host == d or host.endswith("." + d) for d in self.fetch_domains) else "deny"

    # -- mcp -------------------------------------------------------------------------

    def _mcp(self, tool: str) -> str:
        server, _, name = tool[len("mcp:"):].partition(".")
        if server.lower() not in self.mcp_servers or not name:
            return "deny"
        if any(fnmatch.fnmatch(name, pattern) for pattern in self.mcp_write_tools):
            return "ask"
        if any(name.startswith(prefix) for prefix in self.mcp_read_prefixes):
            return "allow"
        return "ask"            # outil inconnu d'un serveur connu : dans le doute, l'athlète tranche
