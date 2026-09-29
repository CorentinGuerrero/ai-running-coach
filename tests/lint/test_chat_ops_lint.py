"""Palier B — chat avec le coach : configuration, exemple Traefik, scripts.

Verrouille ce qui doit rester cohérent sans lancer quoi que ce soit :
  - les clés `[chat]` / `[sync]` de `config/workspace.toml` (contrat de
    `deploy/chat/SPEC.md`) et leurs valeurs par défaut sûres ;
  - l'exemple Traefik : SSO obligatoire sur le routeur du chat, aucun SSO mais un
    rateLimit sur le routeur d'approbation, matchers de la v3 ;
  - `coach-chat.sh` exécutable, présent dans le lint shell.
"""

from __future__ import annotations

import os
import sys
import re
import unittest
from pathlib import Path

from tests.lint.test_config_schema import CONFIG, REPO

CHAT_KEYS = {
    "enabled": False, "backend": "claude", "model": "claude-sonnet-5-5", "base_url": "",
    "api_key_env": "ANTHROPIC_API_KEY", "port": 8766, "listen": "127.0.0.1", "auth": "local",
    "auth_header": "X-authentik-username", "allowed_users": [], "trusted_proxies": ["127.0.0.1"],
    "allowed_hosts": [], "public_url": "", "daily_budget_eur": 2.0, "usd_eur_rate": 0.92,
    "max_turns": 30, "rate_limit_per_min": 6, "approval_wait_s": 600, "approval_ttl_s": 86400,
    "ntfy_approvals": True, "ntfy_quick_approve": True, "ntfy_token_ttl_s": 1800,
}
SYNC_ADDITIONS = {"model": "", "base_url": "", "api_key_env": "", "daily_budget_eur": 0.5}


def _norm(value):
    """Le repli TOML (Python < 3.11) rend booléens et flottants sous forme de chaîne."""
    if isinstance(value, str):
        if value in ("true", "false"):
            return value == "true"
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        if re.fullmatch(r"-?\d+\.\d+", value):
            return float(value)
    return value


class TestChatConfig(unittest.TestCase):
    def test_chat_section_matches_the_spec(self):
        chat = CONFIG.get("chat")
        self.assertIsNotNone(chat, "[chat] absent de config/workspace.toml")
        for key, expected in CHAT_KEYS.items():
            with self.subTest(key=key):
                self.assertIn(key, chat)
                self.assertEqual(_norm(chat[key]), expected)

    def test_chat_is_disabled_and_local_by_default(self):
        self.assertIs(_norm(CONFIG["chat"]["enabled"]), False)
        self.assertEqual(CONFIG["chat"]["auth"], "local")

    def test_sync_additions(self):
        for key, expected in SYNC_ADDITIONS.items():
            with self.subTest(key=key):
                self.assertIn(key, CONFIG["sync"])
                self.assertEqual(_norm(CONFIG["sync"][key]), expected)

    def test_no_secret_in_the_versioned_config(self):
        text = (REPO / "config/workspace.toml").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.strip().startswith("#"):
                continue
            self.assertNotRegex(line, r"sk-[A-Za-z0-9_-]{8,}", "clé API apparente dans workspace.toml")

    def test_sync_runner_doc_lists_opencode(self):
        text = (REPO / "config/workspace.toml").read_text(encoding="utf-8")
        self.assertRegex(text, r'"opencode"')


class TestTraefikExample(unittest.TestCase):
    def setUp(self):
        self.text = (REPO / "deploy/chat/traefik/dynamic.yml").read_text(encoding="utf-8")
        # Deux blocs de routeur, découpés sur leur nom.
        match = re.search(r"^    arc-chat:\n(.*?)^    arc-chat-approve:\n(.*?)^  middlewares:", self.text,
                          re.S | re.M)
        self.assertIsNotNone(match, "routeurs arc-chat / arc-chat-approve introuvables")
        self.chat, self.approve = match.group(1), match.group(2)

    def test_chat_router_requires_sso(self):
        self.assertIn("PathPrefix(`/api/chat`)", self.chat)
        self.assertRegex(self.chat, r"(?m)^\s+- \S+@file\s*$")
        # Le nom d'exemple est volontairement invalide : il faut le remplacer.
        self.assertIn("SSO_MIDDLEWARE_A_REMPLACER@file", self.chat)

    def test_approve_router_has_no_sso_but_a_rate_limit(self):
        self.assertIn("PathRegexp(", self.approve)
        self.assertIn("Method(`POST`)", self.approve)
        self.assertNotIn("SSO_MIDDLEWARE", self.approve)
        self.assertNotIn("authentik", self.approve.lower())
        self.assertIn("arc-chat-approve-ratelimit", self.approve)
        self.assertRegex(self.text, r"rateLimit:\n\s+average: \d+")

    def test_approve_router_outranks_the_chat_router(self):
        chat_prio = int(re.search(r"priority: (\d+)", self.chat).group(1))
        approve_prio = int(re.search(r"priority: (\d+)", self.approve).group(1))
        self.assertGreater(approve_prio, chat_prio)

    def _router_regex(self) -> "re.Pattern":
        """Le motif RÉEL du routeur, extrait de dynamic.yml (jamais recopié dans le test)."""
        match = re.search(r"PathRegexp\(`([^`]+)`\)", self.approve)
        self.assertIsNotNone(match, "PathRegexp introuvable dans le routeur d'approbation")
        return re.compile(match.group(1))

    def test_approve_pattern_matches_a_real_token(self):
        """Régression : le jeton du service est `<id>.<secret>` ; un motif sans « . » renvoyait au SSO."""
        import tempfile
        sys.path.insert(0, str(REPO / "scripts"))
        import arc_chat
        pattern = self._router_regex()
        with tempfile.TemporaryDirectory() as tmp:
            store = arc_chat.ApprovalStore(Path(tmp) / "approvals.json")
            _, tokens = store.create("sess-1234567", "mcp:garmin.schedule_workouts", {"a": 1}, "x", [],
                                     3600, 1800)
            for action in ("allow", "deny"):
                with self.subTest(action=action):
                    self.assertRegex(tokens[action], r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
                    self.assertTrue(pattern.match(f"/api/chat/approve/{tokens[action]}/{action}"),
                                    "le routeur sans SSO ne reconnaît pas un vrai jeton")

    def test_approve_pattern_stays_strict(self):
        pattern = self._router_regex()
        self.assertFalse(pattern.match("/api/chat/approve/Ab3/allow"))          # pas de point
        self.assertFalse(pattern.match("/api/chat/approve/Ab3.x9/allow/../../status"))
        self.assertFalse(pattern.match("/api/chat/approve/Ab3.x9/maybe"))
        self.assertFalse(pattern.match("/api/chat/approve/Ab3.x9.zz/allow"))
        self.assertFalse(pattern.match("/api/chat/approve/.x9/allow"))
        self.assertFalse(pattern.match("/api/chat/approve/Ab3./allow"))
        self.assertFalse(pattern.match("/api/chat/approve/A/b.c/allow"))
        self.assertFalse(pattern.match("/api/chat/approve/Ab3.x9/allow/"))
        self.assertTrue(pattern.match("/api/chat/approve/Ab3_-x9Zq.k-_9/deny"))


class TestChatScripts(unittest.TestCase):
    def test_coach_chat_is_executable(self):
        path = REPO / "scripts/coach-chat.sh"
        self.assertTrue(path.is_file())
        self.assertTrue(os.access(path, os.X_OK), "scripts/coach-chat.sh n'est pas exécutable")

    def test_install_help_documents_the_new_flags(self):
        text = (REPO / "install.sh").read_text(encoding="utf-8")
        usage = text.split("usage() {")[1].split("USAGE\n    exit 0")[0]
        for flag in ("--llm", "--model", "--base-url", "--chat", "--chat-budget", "--sync-budget"):
            with self.subTest(flag=flag):
                self.assertIn(flag, usage)
        self.assertIn("ANTHROPIC_API_KEY", usage)

    def test_no_key_variable_assignment_in_scripts(self):
        for name in ("daily-sync.sh", "coach-chat.sh", "coach_doctor.py"):
            text = (REPO / "scripts" / name).read_text(encoding="utf-8")
            with self.subTest(script=name):
                self.assertNotRegex(text, r"sk-(or|ant)-[A-Za-z0-9]", "clé apparente en dur")


if __name__ == "__main__":
    unittest.main()
