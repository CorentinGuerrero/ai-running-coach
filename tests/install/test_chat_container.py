"""Chat en conteneur (deploy/chat/Dockerfile + deploy/dashboard/compose.chat.yaml).

Vérifications statiques, sans Docker : versions alignées sur le reste du dépôt, et
garde-fous du compose (SSO obligatoire, mêmes chemins que l'hôte, clé hors .env).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DOCKERFILE = (REPO / "deploy/chat/Dockerfile").read_text(encoding="utf-8")
COMPOSE = (REPO / "deploy/dashboard/compose.chat.yaml").read_text(encoding="utf-8")


def _arg(name: str) -> str:
    match = re.search(rf"^ARG {name}=(\S+)$", DOCKERFILE, re.M)
    assert match, f"ARG {name} absent du Dockerfile"
    return match.group(1)


class ChatContainerTests(unittest.TestCase):
    def test_garmin_mcp_aligne_sur_install_sh(self):
        install = (REPO / "install.sh").read_text(encoding="utf-8")
        ref = re.search(r'^GARMIN_MCP_REF="([^"]+)"', install, re.M).group(1)
        self.assertEqual(_arg("GARMIN_MCP_REF"), ref)

    def test_opencode_aligne_sur_la_version_testee(self):
        backend = (REPO / "scripts/arc_chat_opencode.py").read_text(encoding="utf-8")
        tested = re.search(r'^OPENCODE_TESTED_VERSION = "([^"]+)"', backend, re.M).group(1)
        self.assertEqual(_arg("OPENCODE_VERSION"), tested)

    def test_sso_obligatoire_sur_le_routeur_principal(self):
        self.assertIn("routers.arc-chat.middlewares=${TRAEFIK_AUTH_MIDDLEWARE:?", COMPOSE)

    def test_route_a_jeton_restreinte(self):
        rule = next(line for line in COMPOSE.splitlines() if "routers.arc-chat-approve.rule=" in line)
        self.assertIn("Method(`POST`)", rule)
        self.assertIn("(allow|deny)$$", rule)          # « $ » échappé pour compose
        self.assertIn("routers.arc-chat-approve.middlewares=arc-chat-approve-ratelimit", COMPOSE)

    def test_memes_chemins_que_l_hote(self):
        self.assertIn('"${ARC_ENGINE_HOST}:${ARC_ENGINE_HOST}:ro"', COMPOSE)
        self.assertIn('"${ARC_WORKSPACE_HOST}:${ARC_WORKSPACE_HOST}"', COMPOSE)

    def test_cle_par_env_file(self):
        self.assertIn("env_file:", COMPOSE)
        code = "\n".join(line for line in COMPOSE.splitlines() if not line.lstrip().startswith("#"))
        self.assertNotRegex(code, r"(OPENROUTER|ANTHROPIC|OPENAI)_API_KEY\s*[:=]")
        self.assertNotRegex(COMPOSE, r"^\s+ports:", "aucun port publié : Traefik seul")


if __name__ == "__main__":
    unittest.main()
