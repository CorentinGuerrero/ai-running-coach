"""Palier A — source de données `--source garmin|intervals` (#68).

Critère d'acceptation de la story : AUCUN comportement Garmin modifié quand
la source reste `garmin` (le défaut, jamais configuré). Ces tests verrouillent
en particulier (revue PR #116) :

  - une installation Garmin par défaut n'écrit JAMAIS de section `[data]`
    dans `workspace.user.toml` (persist_source() ne s'exécute que si
    `--source` a été passé explicitement) ;
  - un rerun SANS `--source` ne fait jamais revenir un athlète Intervals.icu
    vers Garmin (resolve_source() relit la config existante, comme
    resolve_agents() pour `[agents].enabled`) ;
  - `--source intervals` enregistre le WRAPPER (`run.sh`), jamais le binaire
    `intervals-icu-mcp` directement, et jamais de bloc `env` avec un secret ;
  - `--use-leanproxy` + `--source intervals` est rejeté (leanproxy ne route
    que garmin) ;
  - `--dry-run` n'écrit rien ;
  - changer de source retire l'entrée MCP de l'ANCIENNE source (elle ne doit
    jamais apparaître deux fois dans la config d'un même IDE).
"""

from __future__ import annotations

import json

from tests.lib.asserts import InstallAsserts
from tests.lib.sandbox import Sandbox


def _mcp_servers(sb: Sandbox) -> dict:
    cfg = sb.repo / ".mcp.json"
    if not cfg.is_file():
        return {}
    return json.loads(cfg.read_text()).get("mcpServers", {})


def _source(sb: Sandbox) -> str:
    proc = sb.run([
        "python3", str(sb.repo / "scripts/coach_config.py"), "get",
        "--workspace", str(sb.repo), "--section", "data", "--key", "source",
        "--default", "garmin",
    ])
    return proc.stdout.strip()


class TestDefaultGarminUnchanged(InstallAsserts):
    def test_no_data_section_written_by_default(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--no-auth", "--ide", "claude"))
            user_toml = sb.repo / "config/workspace.user.toml"
            self.assertIsFile(user_toml)
            self.assertNotIn("[data]", user_toml.read_text(encoding="utf-8"))

    def test_default_registers_garmin_not_intervals(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--no-auth", "--ide", "claude"))
            servers = _mcp_servers(sb)
            self.assertIn("garmin", servers)
            self.assertNotIn("intervals", servers)


class TestSourceIntervals(InstallAsserts):
    def test_registers_wrapper_not_the_raw_binary(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--source", "intervals", "--no-auth", "--ide", "claude"))
            servers = _mcp_servers(sb)
            self.assertIn("intervals", servers)
            self.assertNotIn("garmin", servers)
            command = servers["intervals"]["command"]
            self.assertTrue(command.endswith("intervals-icu-mcp/run.sh"), command)
            self.assertNotIn("env", servers["intervals"], "un secret ne doit jamais être écrit ici")
            wrapper = sb.home / ".config/ai-running-coach/intervals-icu-mcp/run.sh"
            self.assertIsFile(wrapper)
            self.assertTrue(wrapper.stat().st_mode & 0o111, "wrapper non exécutable")

    def test_persists_source_only_when_explicit(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--source", "intervals", "--no-auth"))
            self.assertEqual(_source(sb), "intervals")

    def test_rerun_without_source_does_not_revert_to_garmin(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--source", "intervals", "--no-auth", "--ide", "claude"))
            # Deuxième passage SANS --source : ne doit RIEN changer.
            self.assertSucceeded(sb.install("--no-auth", "--ide", "claude"))
            self.assertEqual(_source(sb), "intervals")
            servers = _mcp_servers(sb)
            self.assertIn("intervals", servers)
            self.assertNotIn("garmin", servers)

    def test_leanproxy_rejected_with_intervals_source(self):
        with Sandbox() as sb:
            proc = sb.install("--source", "intervals", "--use-leanproxy", "--no-auth", "--dry-run")
            self.assertFailed(proc, "--use-leanproxy + --source intervals aurait dû être rejeté")
            self.assertOutputContains(proc, "intervals")

    def test_dry_run_writes_nothing(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--source", "intervals", "--dry-run", "--ide", "claude"))
            self.assertFalse((sb.repo / ".mcp.json").exists())
            self.assertFalse((sb.repo / "config/workspace.user.toml").exists())
            self.assertFalse(
                (sb.home / ".config/ai-running-coach/intervals-icu-mcp/run.sh").exists()
            )


class TestSwitchingSource(InstallAsserts):
    def test_switching_to_garmin_removes_the_intervals_entry(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--source", "intervals", "--no-auth", "--ide", "claude"))
            self.assertIn("intervals", _mcp_servers(sb))
            self.assertSucceeded(sb.install("--source", "garmin", "--no-auth", "--ide", "claude"))
            servers = _mcp_servers(sb)
            self.assertIn("garmin", servers)
            self.assertNotIn("intervals", servers, "l'ancienne source doit être retirée, pas seulement ajoutée à côté")
            self.assertEqual(_source(sb), "garmin")

    def test_switching_to_intervals_removes_the_garmin_entry(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--no-auth", "--ide", "claude"))
            self.assertIn("garmin", _mcp_servers(sb))
            self.assertSucceeded(sb.install("--source", "intervals", "--no-auth", "--ide", "claude"))
            servers = _mcp_servers(sb)
            self.assertIn("intervals", servers)
            self.assertNotIn("garmin", servers)


class TestInvalidSource(InstallAsserts):
    def test_unknown_source_is_rejected(self):
        with Sandbox() as sb:
            proc = sb.install("--source", "bogus", "--no-auth", "--dry-run")
            self.assertFailed(proc, "source inconnue aurait dû être rejetée")
