#!/usr/bin/env python3
"""Service HTTP du chat coach : sessions, flux SSE, approbations, budget.

Processus SÉPARÉ de `arc_serve.py` (le tableau de bord reste en lecture seule et
sans clé d'API). Il parle au navigateur avec le protocole d'événements de
`scripts/arc_chat_backend.py` et délègue le modèle à un backend (`mock`,
`claude`, `opencode`). Contrat complet : `deploy/chat/SPEC.md`.

    arc_chat.py [--workspace DIR] [--port N] [--listen ADRESSE] [--backend NOM]

La ligne `URL: http://127.0.0.1:<port>/` est imprimée dès que le serveur écoute
(`--port 0` : port choisi par le système, tests).

Sécurité (deploy/chat/PLAN.md §2.4) :
- `auth = "local"` : loopback uniquement, aucune identité ; le service refuse de
  démarrer si `listen` n'est pas une adresse de boucle locale.
- `auth = "proxy"` : la source doit appartenir à `trusted_proxies` et porter
  l'en-tête d'identité posé par le forward-auth (`auth_header`), présent dans
  `allowed_users` quand la liste n'est pas vide.
- Toute requête POST exige `X-ARC-Chat: 1` ; un `Origin` présent doit égaler
  l'hôte, un `Sec-Fetch-Site` présent doit valoir `same-origin`. Aucun CORS.
- L'en-tête Host est vérifié (`allowed_hosts`, sinon `public_url` + boucle locale).
- Les clés d'API viennent de `~/.config/ai-running-coach/llm.env` (jamais du TOML).
  Rien de secret ni de médical n'est journalisé.

Persistance sous `<workspace>/.arc/chat/` (jetable, gitignoré) : sessions,
approbations, dépense du jour.

Bibliothèque standard uniquement (CONTRIBUTING.md).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import queue
import re
import secrets
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from collections import deque
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_chat_backend import (EVENT_TYPES, BackendError, ChatBackend, TurnContext,  # noqa: E402
                              load_backend, payload_hash)
from arc_chat_policy import Policy  # noqa: E402
from coach_config import ConfigError, read_toml  # noqa: E402

ENGINE = Path(__file__).resolve().parent.parent
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
API = "/api/chat"
PING_INTERVAL_S = float(os.environ.get("ARC_CHAT_PING_S", "15"))
MAX_BODY_BYTES = 64 * 1024
MAX_TEXT_CHARS = 8000
ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,40}$")
ISO = "%Y-%m-%dT%H:%M:%SZ"

# Valeurs par défaut de `[chat]` (config/workspace.toml peut les surcharger ; ce
# tableau garde le service utilisable même si la section n'y est pas encore).
CHAT_DEFAULTS = {
    "enabled": False, "backend": "claude", "model": "claude-sonnet-5-5", "base_url": "",
    "api_key_env": "ANTHROPIC_API_KEY", "port": 8766, "listen": "127.0.0.1",
    "auth": "local", "auth_header": "X-authentik-username", "allowed_users": [],
    "trusted_proxies": ["127.0.0.1"], "allowed_hosts": [], "public_url": "",
    "daily_budget_eur": 2.0, "usd_eur_rate": 0.92, "max_turns": 30, "rate_limit_per_min": 6,
    "approval_wait_s": 600, "approval_ttl_s": 86400, "ntfy_approvals": True,
    "ntfy_quick_approve": True, "ntfy_token_ttl_s": 1800,
    # Délai avant le push ntfy quand un onglet est attaché (SPEC : 60 s). Clé propre au service.
    "ntfy_delay_s": 60,
}


def log(message: str) -> None:
    """Journal sur stderr : jamais de jeton, de clé ni de contenu de santé."""
    print(f"arc_chat: {message}", file=sys.stderr, flush=True)


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime(ISO)


# ---------------------------------------------------------------------------
# Configuration et environnement
# ---------------------------------------------------------------------------

def _merged_sections(workspace: Path) -> dict:
    """workspace.toml puis workspace.user.toml, clé par clé (même règle que config.sh)."""
    shared = workspace / "config/workspace.toml"
    if not shared.exists():
        shared = ENGINE / "config/workspace.toml"
    merged: dict = {}
    for path in (shared, workspace / "config/workspace.user.toml"):
        for section, values in read_toml(path).items():
            if isinstance(values, dict):
                merged.setdefault(section, {}).update(values)
    return merged


def _coerce(default, value):
    """Ramène une valeur TOML au type du défaut (le repli TOML < 3.11 rend les flottants en chaînes)."""
    try:
        if isinstance(default, bool):
            return value if isinstance(value, bool) else str(value).strip().lower() in ("1", "true", "yes")
        if isinstance(default, int):
            return int(float(value))
        if isinstance(default, float):
            return float(value)
        if isinstance(default, list):
            return [str(v) for v in value] if isinstance(value, (list, tuple)) else ([str(value)] if value else [])
        return str(value)
    except (TypeError, ValueError):
        return default


def load_chat_config(workspace: Path, sections: Optional[dict] = None) -> dict:
    """Section `[chat]` résolue : défauts du service < workspace.toml < workspace.user.toml."""
    raw = (sections if sections is not None else _merged_sections(workspace)).get("chat", {})
    cfg = dict(CHAT_DEFAULTS)
    for key, value in raw.items():
        cfg[key] = _coerce(CHAT_DEFAULTS[key], value) if key in CHAT_DEFAULTS else value
    return cfg


def load_notifications(workspace: Path, sections: Optional[dict] = None) -> dict:
    """Section `[notifications]` (ntfy) — mêmes clés que `scripts/notify.sh`."""
    raw = (sections if sections is not None else _merged_sections(workspace)).get("notifications", {})
    token_file = str(raw.get("ntfy_token_file") or "")
    return {
        "provider": str(raw.get("provider") or "none"),
        "ntfy_url": str(raw.get("ntfy_url") or "https://ntfy.sh").rstrip("/"),
        "ntfy_topic": str(raw.get("ntfy_topic") or ""),
        "ntfy_token_file": os.path.expanduser(token_file) if token_file else "",
    }


def parse_llm_env(text: str) -> dict:
    """Lignes `CLE=valeur` ; commentaires `#`, lignes vides, `export ` et guillemets tolérés."""
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def load_llm_env(path: Optional[Path] = None, environ=None) -> tuple:
    """Charge `~/.config/ai-running-coach/llm.env` dans l'environnement ; renvoie (clés posées, avertissements).

    Une variable déjà présente n'est jamais écrasée. Un fichier lisible par d'autres que
    son propriétaire déclenche un avertissement (pas un refus). Les valeurs ne sont pas journalisées.
    """
    environ = os.environ if environ is None else environ
    path = Path(path) if path else Path(environ.get("ARC_LLM_ENV") or "~/.config/ai-running-coach/llm.env").expanduser()
    loaded, warnings = [], []
    if not path.is_file():
        return loaded, warnings
    try:
        if path.stat().st_mode & 0o077:
            warnings.append(f"{path} est lisible par d'autres utilisateurs — chmod 600 recommandé")
        values = parse_llm_env(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return loaded, [f"{path} illisible ({exc.strerror})"]
    for key, value in values.items():
        if key not in environ:
            environ[key] = value
            loaded.append(key)
    return loaded, warnings


# ---------------------------------------------------------------------------
# Sécurité HTTP : Host, authentification, CSRF
# ---------------------------------------------------------------------------

def host_allowlist(port: int, cfg: dict) -> set:
    """En-têtes Host acceptés : boucle locale, `allowed_hosts`, à défaut le nom de `public_url`."""
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    if cfg.get("auth", "local") == "local":
        # En mode local, la page vient du tableau de bord (autre port) qui relaie
        # `/api/chat/*` en conservant son propre Host : tout nom de boucle locale,
        # quel que soit le port, est accepté. Jamais en mode proxy.
        hosts.update({"127.0.0.1", "localhost", "[::1]"})
    declared = [h for h in cfg.get("allowed_hosts", []) if str(h).strip()]
    if not declared and cfg.get("public_url"):
        declared = [urlparse(cfg["public_url"]).netloc]
    for name in declared:
        hosts.add(str(name).strip().lower())
    return hosts


def host_ok(host_header: str, allowed: set) -> bool:
    host = (host_header or "").lower()
    return host in allowed or host.rsplit(":", 1)[0] in allowed


def is_loopback(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def ip_in(ip: str, entries) -> bool:
    """Vrai si `ip` est l'une des adresses ou l'un des réseaux (CIDR) de `entries`."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in entries:
        try:
            if addr in ipaddress.ip_network(str(entry).strip(), strict=False):
                return True
        except ValueError:
            continue
    return False


def authenticate(cfg: dict, peer_ip: str, headers, exempt_identity: bool = False,
                 health_from_loopback: bool = False) -> tuple:
    """(utilisateur, statut, message). Statut 0 = accepté.

    `exempt_identity` : route à jeton (`/approve/…`), sans en-tête d'identité mais avec
    contrôle de la source. `health_from_loopback` : `/healthz` depuis la boucle locale.
    """
    if health_from_loopback and is_loopback(peer_ip):
        return "healthz", 0, ""
    if cfg["auth"] == "local":
        if not is_loopback(peer_ip):
            return None, 403, "Accès refusé : ce service n'accepte que la boucle locale."
        return "local", 0, ""
    if not ip_in(peer_ip, cfg["trusted_proxies"]):
        return None, 403, "Accès refusé : source non autorisée."
    if exempt_identity:
        return "token", 0, ""
    user = (headers.get(cfg["auth_header"]) or "").strip()
    if not user:
        return None, 401, "Authentification requise."
    if cfg["allowed_users"] and user not in cfg["allowed_users"]:
        return None, 403, "Utilisateur non autorisé."
    return user, 0, ""


def check_csrf(headers, token_route: bool = False) -> Optional[str]:
    """Message d'erreur si la requête POST ne respecte pas les règles CSRF, sinon None."""
    if headers.get("X-ARC-Chat") != "1":
        return "En-tête X-ARC-Chat manquant."
    if token_route:
        return None
    origin = headers.get("Origin")
    if origin is not None and (urlparse(origin).netloc.lower() != (headers.get("Host") or "").lower()):
        return "Origine refusée."
    site = headers.get("Sec-Fetch-Site")
    if site is not None and site != "same-origin":
        return "Requête inter-sites refusée."
    return None


class RateLimiter:
    """Fenêtre glissante d'une minute par utilisateur (tours par minute)."""

    def __init__(self, per_min: int, clock=time.monotonic):
        self.per_min = per_min
        self.clock = clock
        self._hits: dict = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.per_min <= 0:
            return True
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= 60:
                hits.popleft()
            if len(hits) >= self.per_min:
                return False
            hits.append(now)
            return True


# ---------------------------------------------------------------------------
# Persistance : `.arc/chat/`
# ---------------------------------------------------------------------------

def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class SpendStore:
    """Dépense du chat du jour (`spend-AAAA-MM-JJ.json`, `{"chat_eur": x}`)."""

    def __init__(self, directory: Path, today=date.today):
        self.dir = directory
        self.today = today
        self._lock = threading.Lock()

    def _path(self) -> Path:
        return self.dir / f"spend-{self.today().isoformat()}.json"

    def spent(self) -> float:
        with self._lock:
            return float(_read_json(self._path(), {}).get("chat_eur", 0.0) or 0.0)

    def add(self, eur: float) -> float:
        if eur <= 0:
            return self.spent()
        with self._lock:
            data = _read_json(self._path(), {})
            data["chat_eur"] = round(float(data.get("chat_eur", 0.0) or 0.0) + eur, 6)
            _atomic_write(self._path(), data)
            return data["chat_eur"]


class SessionStore:
    """`sessions/<id>.json` (méta) et `sessions/<id>.jsonl` (un événement par ligne)."""

    def __init__(self, directory: Path):
        self.dir = directory / "sessions"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _meta_path(self, sid: str) -> Path:
        return self.dir / f"{sid}.json"

    def create(self, backend: str, model: str) -> dict:
        now = iso(time.time())
        meta = {"id": secrets.token_urlsafe(12), "title": "", "created": now, "updated": now,
                "backend": backend, "model": model, "backend_state": {}, "cost_eur": 0.0}
        with self._lock:
            _atomic_write(self._meta_path(meta["id"]), meta)
        return meta

    def get(self, sid: str) -> Optional[dict]:
        if not ID_RE.match(sid or ""):
            return None
        return _read_json(self._meta_path(sid), None)

    def save(self, meta: dict) -> None:
        with self._lock:
            meta["updated"] = iso(time.time())
            _atomic_write(self._meta_path(meta["id"]), meta)

    def update(self, sid: str, **changes) -> Optional[dict]:
        """Lecture-modification-écriture atomique de la méta (titre, coût, état du backend)."""
        with self._lock:
            meta = self.get(sid)
            if meta is None:
                return None
            for key, value in changes.items():
                if key == "add_cost":
                    meta["cost_eur"] = round(float(meta.get("cost_eur", 0.0)) + value, 6)
                elif key == "title" and meta.get("title"):
                    continue                              # le titre reste celui du premier message
                else:
                    meta[key] = value
            self.save(meta)
            return meta

    def list(self) -> list:
        metas = [_read_json(p, None) for p in self.dir.glob("*.json")]
        return sorted((m for m in metas if m), key=lambda m: m.get("updated", ""), reverse=True)

    def append_event(self, sid: str, etype: str, data: dict) -> None:
        line = json.dumps({"ts": iso(time.time()), "type": etype, "data": data}, ensure_ascii=False)
        with self._lock:
            with open(self.dir / f"{sid}.jsonl", "a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def events(self, sid: str) -> list:
        path = self.dir / f"{sid}.jsonl"
        if not path.is_file():
            return []
        events = []
        with self._lock:
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
        return events


OPEN_STATUSES = ("waiting", "pending")


def token_digest(approval_id: str, phash: str, secret: str) -> str:
    """Empreinte stockée d'un jeton : liée à l'identifiant ET à la charge exacte de l'appel."""
    return hashlib.sha256(f"{approval_id}|{phash}|{secret}".encode("utf-8")).hexdigest()


class ApprovalStore:
    """`approvals.json` : propositions en attente, décisions, jetons ntfy (hachés uniquement).

    Statuts : `waiting` (le tour attend), `pending` (le tour est terminé, la proposition reste
    ouverte), puis `allowed`, `denied`, `expired`. Un jeton est `<id>.<secret>` ; seul
    `sha256(id|hash_charge|secret)` est conservé, et les DEUX jetons (appliquer/refuser) sont
    brûlés à la première décision, quelle que soit sa voie.
    """

    def __init__(self, path: Path, clock=time.time):
        self.path = path
        self.clock = clock
        self._lock = threading.RLock()

    def _load(self) -> dict:
        return _read_json(self.path, {})

    def _save(self, data: dict) -> None:
        _atomic_write(self.path, data)

    def create(self, session_id: str, tool: str, tool_input: dict, summary: str, diff: list,
               ttl_s: float, token_ttl_s: Optional[float] = None) -> tuple:
        """Crée une proposition ; renvoie (enregistrement, {"allow": jeton, "deny": jeton}).

        Les jetons ne sont renvoyés qu'ici (jamais stockés en clair) ; `token_ttl_s=None` : aucun jeton.
        """
        now = self.clock()
        approval_id = secrets.token_urlsafe(12)
        phash = payload_hash(tool, tool_input)
        tokens, hashes = {}, {}
        if token_ttl_s is not None:
            for action in ("allow", "deny"):
                secret = secrets.token_urlsafe(24)
                tokens[action] = f"{approval_id}.{secret}"
                hashes[action] = token_digest(approval_id, phash, secret)
        record = {
            "session_id": session_id, "tool": tool, "input": tool_input, "hash": phash,
            "summary": summary, "diff": diff, "status": "waiting",
            "created": iso(now), "expires_at": iso(now + ttl_s), "expires_ts": now + ttl_s,
            "token_expires_ts": now + (token_ttl_s or 0), "token_hashes": hashes, "burned_hashes": {},
        }
        with self._lock:
            data = self._load()
            data[approval_id] = record
            self._save(data)
        return dict(record, id=approval_id), tokens

    def get(self, approval_id: str) -> Optional[dict]:
        if not ID_RE.match(approval_id or ""):
            return None
        self.expire_due()
        record = self._load().get(approval_id)
        return dict(record, id=approval_id) if record else None

    def list(self, session_id: Optional[str] = None) -> list:
        self.expire_due()
        return [dict(rec, id=aid) for aid, rec in self._load().items()
                if session_id is None or rec.get("session_id") == session_id]

    def expire_due(self) -> list:
        """Passe en `expired` les propositions ouvertes dont le délai est écoulé ; les renvoie."""
        expired = []
        with self._lock:
            data = self._load()
            now = self.clock()
            for aid, rec in data.items():
                if rec["status"] in OPEN_STATUSES and rec["expires_ts"] <= now:
                    self._close(rec, "expired")
                    expired.append(dict(rec, id=aid))
            if expired:
                self._save(data)
        return expired

    @staticmethod
    def _close(rec: dict, status: str) -> None:
        rec["status"] = status
        rec["resolved_at"] = iso(time.time())
        rec["burned_hashes"] = dict(rec.get("token_hashes") or {}) or rec.get("burned_hashes", {})
        rec["token_hashes"] = {}                                     # brûle les deux jetons

    def mark_pending(self, approval_id: str) -> bool:
        with self._lock:
            data = self._load()
            rec = data.get(approval_id)
            if not rec or rec["status"] != "waiting":
                return False
            rec["status"] = "pending"
            self._save(data)
            return True

    def resolve(self, approval_id: str, decision: str) -> tuple:
        """(résultat, enregistrement) ; résultat : ok | unknown | closed | expired."""
        self.expire_due()
        with self._lock:
            data = self._load()
            rec = data.get(approval_id)
            if rec is None:
                return "unknown", None
            if rec["status"] not in OPEN_STATUSES:
                return ("expired" if rec["status"] == "expired" else "closed"), dict(rec, id=approval_id)
            previous = rec["status"]
            self._close(rec, "allowed" if decision == "allow" else "denied")
            self._save(data)
            return "ok", dict(rec, id=approval_id, previous_status=previous)

    def verify_token(self, token: str, action: str) -> tuple:
        """(résultat, enregistrement) ; résultat : ok | unknown | used | expired | mismatch.

        `mismatch` : le jeton était valide pour la charge d'origine, mais la charge stockée a
        changé depuis (un jeton ne peut pas approuver une autre modification).
        """
        approval_id, _, secret = (token or "").partition(".")
        if action not in ("allow", "deny") or not secret or not ID_RE.match(approval_id):
            return "unknown", None
        self.expire_due()
        rec = self._load().get(approval_id)
        if rec is None:
            return "unknown", None
        stored = token_digest(approval_id, rec["hash"], secret)
        burned = rec.get("burned_hashes", {}).get(action)
        if burned and hmac.compare_digest(burned, stored):
            return "used", dict(rec, id=approval_id)
        expected = (rec.get("token_hashes") or {}).get(action)
        if not expected:
            return "unknown", None
        if not hmac.compare_digest(expected, stored):
            return "unknown", None
        if payload_hash(rec["tool"], rec["input"]) != rec["hash"]:
            return "mismatch", dict(rec, id=approval_id)
        if rec["status"] not in OPEN_STATUSES:
            return "used", dict(rec, id=approval_id)
        if rec["token_expires_ts"] <= self.clock():
            return "expired", dict(rec, id=approval_id)
        return "ok", dict(rec, id=approval_id)

    def reopen_orphans(self) -> int:
        """Au démarrage : un tour `waiting` n'a plus de fil qui l'attend → `pending`."""
        with self._lock:
            data = self._load()
            count = 0
            for rec in data.values():
                if rec["status"] == "waiting":
                    rec["status"] = "pending"
                    count += 1
            if count:
                self._save(data)
        return count


# ---------------------------------------------------------------------------
# ntfy
# ---------------------------------------------------------------------------

def build_actions(public_url: str, approval_id: str, tokens: Optional[dict]) -> str:
    """En-tête `Actions` de ntfy : `view` (Ouvrir) et, si des jetons existent, `http` (Appliquer/Refuser)."""
    base = public_url.rstrip("/")
    actions = [f"view, Ouvrir, {base}/chat.html#approval={approval_id}"]
    if tokens:
        for label, action in (("Appliquer", "allow"), ("Refuser", "deny")):
            actions.append(f"http, {label}, {base}{API}/approve/{tokens[action]}/{action}, "
                           "method=POST, headers.X-ARC-Chat=1, clear=true")
    return "; ".join(actions)


def send_ntfy(notif: dict, title: str, body: str, actions: str = "", timeout: float = 10) -> bool:
    """Envoie une notification ntfy ; ne lève jamais (le service ne doit pas tomber pour un push)."""
    if notif.get("provider") != "ntfy" or not notif.get("ntfy_topic"):
        return False
    headers = {"Title": title, "Priority": "4", "Tags": "runner"}
    if actions:
        headers["Actions"] = actions
    if notif.get("ntfy_token_file"):
        try:
            token = Path(notif["ntfy_token_file"]).read_text(encoding="utf-8").strip()
            headers["Authorization"] = f"Bearer {token}"
        except OSError:
            log("ntfy : fichier token illisible")
            return False
    url = f"{notif['ntfy_url']}/{notif['ntfy_topic']}"
    request = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return True
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log(f"ntfy : envoi impossible ({type(exc).__name__})")
        return False


# ---------------------------------------------------------------------------
# Tours de conversation
# ---------------------------------------------------------------------------

class Turn:
    """Un tour en cours : journalise chaque événement et le diffuse aux flux SSE attachés."""

    def __init__(self, service: "ChatService", session_id: str):
        self.service = service
        self.session_id = session_id
        self.cancelled = threading.Event()
        self.subscribers: list = []
        self.terminal = False               # `done` ou `error` déjà émis
        self.pending_created = False
        self.lock = threading.Lock()

    def subscribe(self) -> "queue.Queue":
        q: queue.Queue = queue.Queue()
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q) -> None:
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def emit(self, etype: str, data: dict) -> None:
        if etype not in EVENT_TYPES:
            log(f"événement inconnu ignoré : {etype}")
            return
        data = data if isinstance(data, dict) else {}
        with self.lock:
            self.service.sessions.append_event(self.session_id, etype, data)
            if etype in ("done", "error"):
                self.terminal = True
            for q in list(self.subscribers):
                q.put((etype, data))
        if etype == "usage":
            self.service.record_usage(self.session_id, data)

    def close(self) -> None:
        with self.lock:
            for q in list(self.subscribers):
                q.put(None)


class ChatService:
    """État partagé par les requêtes : configuration, stockage, backend, tours, approbations."""

    def __init__(self, workspace: Path, cfg: dict, backend: ChatBackend, notif: Optional[dict] = None,
                 policy: Optional[Policy] = None):
        self.workspace = Path(workspace)
        self.cfg = cfg
        self.backend = backend
        self.notif = notif if notif is not None else {"provider": "none"}
        self.policy = policy or Policy.load(ENGINE, self.workspace)
        root = self.workspace / ".arc" / "chat"
        root.mkdir(parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        self.sessions = SessionStore(root)
        self.approvals = ApprovalStore(root / "approvals.json")
        self.spend = SpendStore(root)
        self.limiter = RateLimiter(int(cfg["rate_limit_per_min"]))
        self.approve_limiter = RateLimiter(30)          # route à jeton : essais par minute, toutes sources
        self._lock = threading.Lock()
        self._slots: dict = {}                          # session_id → verrou « un tour à la fois »
        self.turns: dict = {}                           # session_id → Turn en cours
        self._waiters: dict = {}                        # approval_id → (Event, [décision])
        self._raw_tokens: dict = {}                     # approval_id → jetons en clair (mémoire seulement)
        self._notified: set = set()
        self.approvals.reopen_orphans()

    # -- dépense ---------------------------------------------------------------

    def record_usage(self, sid: str, data: dict) -> None:
        try:
            eur = float(data.get("cost_eur") or 0.0)
        except (TypeError, ValueError):
            eur = 0.0
        if eur > 0:
            self.spend.add(eur)
            self.sessions.update(sid, add_cost=eur)

    def budget_exhausted(self) -> bool:
        return self.spend.spent() >= float(self.cfg["daily_budget_eur"])

    # -- tours -----------------------------------------------------------------

    def _slot(self, sid: str) -> threading.Lock:
        with self._lock:
            return self._slots.setdefault(sid, threading.Lock())

    def begin_turn(self, sid: str, user: str, text: str, preapproved=None, resume: bool = False) -> tuple:
        """Démarre un tour. Renvoie (code, Turn|None, file d'événements|None).

        code : ok | busy (409) | rate (429) | unknown (404). Un tour de reprise (`resume`)
        attend son tour de parole au lieu d'échouer et n'entre pas dans la limite de débit.
        """
        if self.sessions.get(sid) is None:
            return "unknown", None, None
        slot = self._slot(sid)
        if not slot.acquire(timeout=120 if resume else 0):
            return "busy", None, None
        if not resume and not self.limiter.allow(user):
            slot.release()
            return "rate", None, None
        turn = Turn(self, sid)
        q = None if resume else turn.subscribe()
        with self._lock:
            self.turns[sid] = turn
        self.sessions.append_event(sid, "user_message", {"text": text, **({"synthetic": True} if resume else {})})
        self.sessions.update(sid, title=re.sub(r"\s+", " ", text).strip()[:60] or "Conversation")
        threading.Thread(target=self._run_turn, args=(turn, text, set(preapproved or ())),
                         name=f"chat-turn-{sid[:6]}", daemon=True).start()
        return "ok", turn, q

    def _run_turn(self, turn: Turn, text: str, preapproved: set) -> None:
        sid = turn.session_id
        try:
            if self.budget_exhausted():
                turn.emit("error", {"message": (
                    f"Budget quotidien du chat atteint ({self.spend.spent():.2f} € sur "
                    f"{float(self.cfg['daily_budget_eur']):.2f} €). Réessaie demain ou relève "
                    "[chat].daily_budget_eur.")})
                turn.emit("done", {"reason": "budget"})
                return
            meta = self.sessions.get(sid) or {}
            state = meta.get("backend_state")
            state = state if isinstance(state, dict) else {}
            ctx = TurnContext(
                session_id=sid, workspace=self.workspace, config=self.cfg, emit=turn.emit,
                decide=lambda tool, tool_input: self.policy.decide(tool, tool_input, preapproved),
                request_approval=lambda tool, tool_input, summary, diff: self._request_approval(
                    turn, tool, tool_input, summary, diff),
                cancelled=turn.cancelled, backend_state=state,
                language=str(self.cfg.get("language", "fr")))
            try:
                self.backend.run_turn(ctx, text)
            finally:
                self.sessions.update(sid, backend_state=ctx.backend_state)
            if not turn.terminal:
                reason = ("interrupted" if turn.cancelled.is_set()
                          else "pending_approval" if turn.pending_created else "end_turn")
                turn.emit("done", {"reason": reason})
        except BackendError as exc:
            turn.emit("error", {"message": str(exc)})
        except Exception:                                # noqa: BLE001 — jamais de trace vers le navigateur
            log("erreur inattendue dans un tour :\n" + traceback.format_exc())
            turn.emit("error", {"message": "Erreur interne du service de chat."})
        finally:
            with self._lock:
                self.turns.pop(sid, None)
            turn.close()
            self._slot(sid).release()

    def interrupt(self, sid: str) -> bool:
        with self._lock:
            turn = self.turns.get(sid)
        if turn is None:
            return False
        turn.cancelled.set()
        return True

    # -- approbations ------------------------------------------------------------

    def _emit_session(self, sid: str, etype: str, data: dict) -> None:
        """Émet sur le tour vivant de la session (flux + journal), sinon dans le journal seul."""
        with self._lock:
            turn = self.turns.get(sid)
        if turn is not None:
            turn.emit(etype, data)
        else:
            self.sessions.append_event(sid, etype, data)

    def ntfy_enabled(self) -> bool:
        return bool(self.cfg["ntfy_approvals"] and self.notif.get("provider") == "ntfy"
                    and self.notif.get("ntfy_topic"))

    def notify_approval(self, approval_id: str, summary: str) -> None:
        """Push ntfy (une seule fois par proposition) : résumé seul, jamais de valeur de santé."""
        if not self.ntfy_enabled() or approval_id in self._notified:
            return
        self._notified.add(approval_id)
        public = str(self.cfg["public_url"]).rstrip("/")
        actions = build_actions(public, approval_id, self._raw_tokens.get(approval_id)) if public else ""
        if send_ntfy(self.notif, "Coach : confirmation demandée", summary, actions):
            log(f"ntfy envoyé pour la proposition {approval_id[:4]}…")

    def _request_approval(self, turn: Turn, tool: str, tool_input: dict, summary: str, diff: list) -> str:
        cfg = self.cfg
        quick = bool(cfg["ntfy_quick_approve"] and self.ntfy_enabled() and cfg["public_url"])
        record, tokens = self.approvals.create(
            turn.session_id, tool, tool_input, summary, diff, float(cfg["approval_ttl_s"]),
            float(cfg["ntfy_token_ttl_s"]) if quick else None)
        aid = record["id"]
        if tokens:
            self._raw_tokens[aid] = tokens
        event, box = threading.Event(), []
        self._waiters[aid] = (event, box)
        turn.emit("approval_request", {"approval_id": aid, "tool": tool, "summary": summary,
                                       "diff": diff, "expires_at": record["expires_at"]})
        start = time.monotonic()
        wait = float(cfg["approval_wait_s"])
        delay = float(cfg["ntfy_delay_s"])
        try:
            if not turn.subscribers:
                self.notify_approval(aid, summary)       # personne devant l'écran : push tout de suite
            while True:
                if event.is_set():
                    return box[0] if box else "deny"
                if turn.cancelled.is_set():
                    self.resolve_approval(aid, "deny", via="cancel")
                    return "deny"
                elapsed = time.monotonic() - start
                if elapsed >= wait:
                    break
                if aid not in self._notified and elapsed >= delay:
                    self.notify_approval(aid, summary)
                event.wait(min(0.2, wait - elapsed))
            # Délai d'attente en ligne écoulé : la proposition reste ouverte (reprise ultérieure).
            if self.approvals.mark_pending(aid):
                turn.pending_created = True
                turn.emit("approval_resolved", {"approval_id": aid, "decision": "pending"})
                self.notify_approval(aid, summary)
                return "pending"
            return box[0] if box else "deny"             # décision arrivée pile au bord
        finally:
            self._waiters.pop(aid, None)

    def resolve_approval(self, approval_id: str, decision: str, via: str = "page") -> tuple:
        """Applique une décision (page, ntfy ou annulation). Renvoie (résultat, enregistrement)."""
        result, rec = self.approvals.resolve(approval_id, decision)
        if result == "expired" and rec is not None:
            return result, rec
        if result != "ok":
            return result, rec
        self._raw_tokens.pop(approval_id, None)
        sid = rec["session_id"]
        self._emit_session(sid, "approval_resolved", {"approval_id": approval_id, "decision": decision})
        log(f"approbation {approval_id[:4]}… : {decision} ({via})")
        waiter = self._waiters.get(approval_id)
        if waiter and rec.get("previous_status") == "waiting":
            waiter[1].append(decision)
            waiter[0].set()
        elif decision == "allow" and via != "cancel":
            self._resume_after_approval(rec)
        return result, rec

    def _resume_after_approval(self, rec: dict) -> None:
        """Approbation tardive : nouveau tour dont SEUL l'appel approuvé (même hash) est pré-autorisé."""
        message = (f"[approbation] L'athlète a approuvé la proposition {rec['id']} ({rec['summary']}). "
                   "Exécute exactement cet appel maintenant.")

        def go():
            code, _, _ = self.begin_turn(rec["session_id"], "resume", message,
                                         preapproved={rec["hash"]}, resume=True)
            if code != "ok":
                log(f"reprise impossible pour {rec['id'][:4]}… ({code})")

        threading.Thread(target=go, name="chat-resume", daemon=True).start()

    def sweep_expired(self) -> None:
        for rec in self.approvals.expire_due():
            self._emit_session(rec["session_id"], "approval_resolved",
                               {"approval_id": rec["id"], "decision": "expired"})

    # -- vues ---------------------------------------------------------------------

    def public_approval(self, rec: dict) -> dict:
        return {"id": rec["id"], "session_id": rec["session_id"], "tool": rec["tool"],
                "summary": rec["summary"], "diff": rec["diff"], "status": rec["status"],
                "created": rec["created"], "expires_at": rec["expires_at"]}

    def session_summary(self, meta: dict) -> dict:
        pending = sum(1 for a in self.approvals.list(meta["id"]) if a["status"] in OPEN_STATUSES)
        return {"id": meta["id"], "title": meta.get("title", ""), "created": meta["created"],
                "updated": meta["updated"], "cost_eur": meta.get("cost_eur", 0.0),
                "pending_approvals": pending}

    def status(self, user: str) -> dict:
        return {"enabled": bool(self.cfg["enabled"]), "backend": self.backend.name,
                "model": self.cfg["model"], "user": user,
                "budget": {"spent_eur": round(self.spend.spent(), 4),
                           "limit_eur": float(self.cfg["daily_budget_eur"])},
                "ntfy": self.ntfy_enabled()}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(rf"^{API}/approve/([^/]+)/(allow|deny)$")
TOKEN_PATH_REDACT = re.compile(rf"({API}/approve/)[^/\s]+")


class Handler(BaseHTTPRequestHandler):
    server_version = "arc-chat"
    service: ChatService = None
    allowed_hosts: set = set()

    def log_message(self, fmt, *args):
        pass

    def log_request(self, code="-", size="-"):
        # Le jeton ntfy fait partie du chemin : il ne doit jamais atteindre les journaux.
        safe = TOKEN_PATH_REDACT.sub(lambda m: m.group(1) + "***", self.path.split("?")[0])
        log(f"{self.command} {safe} {code}")

    # -- réponses -------------------------------------------------------------------

    def _headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")

    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._headers()
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    def _read_body(self) -> Optional[dict]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            self._error(413, "Corps de requête trop volumineux.")
            return None
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._error(400, "JSON invalide.")
            return None
        if not isinstance(data, dict):
            self._error(400, "Objet JSON attendu.")
            return None
        return data

    # -- garde commune ----------------------------------------------------------------

    def _gate(self, post: bool) -> Optional[str]:
        """Contrôles Host → source/identité → CSRF. Renvoie l'utilisateur, ou None (réponse déjà envoyée)."""
        svc = self.service
        if not host_ok(self.headers.get("Host"), self.allowed_hosts):
            self._error(403, "Hôte non autorisé.")
            return None
        path = self.path.split("?")[0]
        token_route = bool(TOKEN_RE.match(path))
        health = path in (f"{API}/healthz", "/healthz")
        user, status, message = authenticate(svc.cfg, self.client_address[0], self.headers,
                                             exempt_identity=token_route, health_from_loopback=health)
        if status:
            self._error(status, message)
            return None
        if post:
            problem = check_csrf(self.headers, token_route)
            if problem:
                self._error(403, problem)
                return None
        return user

    # -- routage -----------------------------------------------------------------------

    def do_GET(self):
        user = self._gate(post=False)
        if user is None:
            return
        svc, path = self.service, self.path.split("?")[0]
        if path in (f"{API}/healthz", "/healthz"):
            ok, message = svc.backend.check()
            return self._json(200 if ok else 503, {"ok": bool(ok), "backend_check": message})
        if path == f"{API}/status":
            return self._json(200, svc.status(user))
        if path == f"{API}/sessions":
            return self._json(200, {"sessions": [svc.session_summary(m) for m in svc.sessions.list()]})
        match = re.match(rf"^{API}/sessions/([^/]+)$", path)
        if match:
            meta = svc.sessions.get(match.group(1))
            if meta is None:
                return self._error(404, "Conversation introuvable.")
            body = {k: v for k, v in meta.items() if k != "backend_state"}
            body["pending_approvals"] = svc.session_summary(meta)["pending_approvals"]
            body["running"] = match.group(1) in svc.turns
            body["events"] = svc.sessions.events(meta["id"])
            return self._json(200, body)
        match = re.match(rf"^{API}/approvals/([^/]+)$", path)
        if match:
            rec = svc.approvals.get(match.group(1))
            if rec is None:
                return self._error(404, "Proposition introuvable.")
            return self._json(200, svc.public_approval(rec))
        self._error(404, "Route inconnue.")

    def do_POST(self):
        user = self._gate(post=True)
        if user is None:
            return
        svc, path = self.service, self.path.split("?")[0]
        match = TOKEN_RE.match(path)
        if match:
            return self._post_token(match.group(1), match.group(2))
        if path == f"{API}/sessions":
            if self._read_body() is None:
                return
            meta = svc.sessions.create(svc.backend.name, str(svc.cfg["model"]))
            return self._json(200, {"id": meta["id"]})
        match = re.match(rf"^{API}/sessions/([^/]+)/messages$", path)
        if match:
            return self._post_message(match.group(1), user)
        match = re.match(rf"^{API}/sessions/([^/]+)/interrupt$", path)
        if match:
            if self._read_body() is None:
                return
            if svc.sessions.get(match.group(1)) is None:
                return self._error(404, "Conversation introuvable.")
            return self._json(200, {"ok": True, "running": svc.interrupt(match.group(1))})
        match = re.match(rf"^{API}/approvals/([^/]+)$", path)
        if match:
            return self._post_approval(match.group(1))
        self._error(404, "Route inconnue.")

    do_PUT = do_DELETE = do_PATCH = lambda self: self._error(405, "Méthode non autorisée.")

    # -- routes ------------------------------------------------------------------------

    def _post_approval(self, approval_id: str) -> None:
        body = self._read_body()
        if body is None:
            return
        decision = body.get("decision")
        if decision not in ("allow", "deny"):
            return self._error(400, "decision : « allow » ou « deny » attendu.")
        result, rec = self.service.resolve_approval(approval_id, decision, via="page")
        self._approval_result(result, rec, decision)

    def _approval_result(self, result: str, rec: Optional[dict], decision: str) -> None:
        if result == "ok":
            return self._json(200, {"ok": True, "decision": decision})
        if result == "unknown":
            return self._error(404, "Proposition introuvable.")
        if result == "expired":
            return self._error(410, "Cette proposition a expiré.")
        self._error(409, "Cette proposition a déjà été traitée.")

    def _post_token(self, token: str, action: str) -> None:
        """Action rapide ntfy : jeton à usage unique, lié à la proposition et à sa charge exacte."""
        svc = self.service
        if not svc.approve_limiter.allow("approve"):
            return self._error(429, "Trop de tentatives.")
        if self._read_body() is None:
            return
        result, rec = svc.approvals.verify_token(token, action)
        if result != "ok":
            log(f"jeton refusé ({result})")
            status = {"unknown": 404, "used": 410, "expired": 410, "mismatch": 409}[result]
            return self._error(status, {"unknown": "Lien invalide.", "used": "Lien déjà utilisé.",
                                        "expired": "Lien expiré.",
                                        "mismatch": "La proposition a changé."}[result])
        outcome, _ = svc.resolve_approval(rec["id"], action, via="ntfy")
        self._approval_result(outcome, rec, action)

    def _post_message(self, sid: str, user: str) -> None:
        svc = self.service
        body = self._read_body()
        if body is None:
            return
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            return self._error(400, "Message vide.")
        if len(text) > MAX_TEXT_CHARS:
            return self._error(413, "Message trop long.")
        code, turn, q = svc.begin_turn(sid, user, text.strip())
        if code == "unknown":
            return self._error(404, "Conversation introuvable.")
        if code == "busy":
            return self._error(409, "Un tour est déjà en cours dans cette conversation.")
        if code == "rate":
            return self._error(429, "Trop de messages : patiente une minute.")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self._headers()
        self.end_headers()
        try:
            while True:
                try:
                    item = q.get(timeout=PING_INTERVAL_S)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                if item is None:
                    break
                etype, data = item
                self.wfile.write(f"event: {etype}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass                                          # l'onglet est parti ; le tour continue
        finally:
            turn.unsubscribe(q)
            self.close_connection = True


# ---------------------------------------------------------------------------
# Démarrage
# ---------------------------------------------------------------------------

def check_exposure(cfg: dict) -> None:
    if cfg["auth"] not in ("local", "proxy"):
        raise ConfigError(f"[chat].auth : « local » ou « proxy » attendu, « {cfg['auth']} » trouvé.")
    if cfg["auth"] == "local" and cfg["listen"] not in LOOPBACK_HOSTS:
        raise ConfigError(
            f"[chat].auth = \"local\" exige une écoute en boucle locale (listen = {cfg['listen']!r}). "
            "Derrière un reverse proxy : auth = \"proxy\" avec trusted_proxies et auth_header.")


def make_server(workspace: Path, cfg: dict, backend: ChatBackend, notif: Optional[dict] = None,
                port: Optional[int] = None, policy: Optional[Policy] = None) -> tuple:
    """(serveur HTTP lié, ChatService). `port=0` : port libre choisi par le système."""
    check_exposure(cfg)
    service = ChatService(workspace, cfg, backend, notif, policy)
    listen = cfg["listen"]

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    # Sous-classe par serveur : deux services dans un même processus (tests) ne se marchent pas dessus.
    bound = type("BoundHandler", (Handler,), {"service": service})
    wanted = int(cfg["port"] if port is None else port)
    try:
        httpd = Server((listen, wanted), bound)
    except OSError as exc:
        raise ConfigError(f"impossible d'écouter sur {listen}:{wanted} ({exc.strerror}).")
    bound.allowed_hosts = host_allowlist(httpd.server_address[1], cfg)
    return httpd, service


def serve(workspace: Path, port: Optional[int] = None, listen: Optional[str] = None,
          backend_name: Optional[str] = None) -> None:
    for warning in load_llm_env()[1]:
        log(f"avertissement : {warning}")
    sections = _merged_sections(workspace)
    cfg = load_chat_config(workspace, sections)
    if listen:
        cfg["listen"] = listen
    if backend_name:
        cfg["backend"] = backend_name
    try:
        backend = load_backend(cfg["backend"], workspace, cfg)
    except BackendError as exc:
        raise ConfigError(str(exc))
    httpd, service = make_server(workspace, cfg, backend, load_notifications(workspace, sections), port)
    stop = threading.Event()

    def sweeper():
        while not stop.wait(30):
            try:
                service.sweep_expired()
            except Exception:                             # noqa: BLE001
                log("balayage des propositions expirées : erreur")

    threading.Thread(target=sweeper, name="chat-sweeper", daemon=True).start()
    shown = "127.0.0.1" if cfg["listen"] in LOOPBACK_HOSTS else cfg["listen"]
    print(f"URL: http://{shown}:{httpd.server_address[1]}/", flush=True)
    log(f"backend {backend.name}, auth {cfg['auth']}, budget {float(cfg['daily_budget_eur']):.2f} €/jour")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        httpd.server_close()
        backend.shutdown()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace")
    parser.add_argument("--port", type=int)
    parser.add_argument("--listen")
    parser.add_argument("--backend")
    args = parser.parse_args(argv)
    from coach_setup import workspace_root
    serve(workspace_root(args.workspace), args.port, args.listen, args.backend)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ConfigError as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        sys.exit(1)
