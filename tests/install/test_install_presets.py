"""Palier A — préréglages d'installation (`--preset laptop|coach-server|docker`, #64).

Chaque préréglage ne fait que composer des options déjà existantes
(`--ide`, `--daily-sync`, `--remote-control`, `--no-auth`, `--use-leanproxy`) —
voir `apply_preset()` dans `install.sh`. Ces tests verrouillent :

  - le mapping réel de chaque préréglage (empreinte d'arborescence, en
    `--dry-run` et en installation réelle) ;
  - la priorité systématique d'une option explicite sur le préréglage,
    quel que soit l'ordre des arguments ;
  - le rejet propre d'un préréglage inconnu.

`ARC_FAKE_UNAME=Darwin` fixe le backend (LaunchAgent, jamais crontab) pour que
les empreintes d'arborescence soient les mêmes sur les machines de CI Linux et
macOS — `tests/lib/sandbox.Sandbox.tree()` ne renvoie que des chemins relatifs
au bac à sable (jamais un chemin absolu de l'hôte), donc les empreintes
ci-dessous sont portables telles quelles.
"""

from __future__ import annotations

from tests.lib.asserts import InstallAsserts
from tests.lib.sandbox import Sandbox

DARWIN = {"ARC_FAKE_UNAME": "Darwin"}

# Empreintes attendues : chemins AJOUTÉS par rapport à un dépôt fraîchement
# copié (avant tout appel à install.sh), pour une installation réelle avec le
# préréglage nommé et rien d'autre. Régénérées en lisant la sortie réelle de
# `sb.tree()` (voir la story #64) — un écart doit être expliqué par un
# changement assumé du mapping du préréglage, jamais par un artefact
# d'environnement (aucun chemin absolu n'y figure).
EXPECTED_ADDED_PATHS = {
    "laptop": {
        "home/.claude.json",
        "home/.config/ai-running-coach",
        "home/.config/ai-running-coach/workspace",
        "home/.config/opencode",
        "home/.config/opencode/opencode.json",
        "repo/.claude",
        "repo/.claude/agents",
        "repo/.claude/agents/coach.md",
        "repo/.claude/agents/course-strategist.md",
        "repo/.claude/agents/medical.md",
        "repo/.claude/agents/nutritionist.md",
        "repo/.claude/skills",
        "repo/.cursor",
        "repo/.cursor/mcp.json",
        "repo/.gemini",
        "repo/.gemini/commands",
        "repo/.gemini/commands/coach.toml",
        "repo/.gemini/commands/course-strategist.toml",
        "repo/.gemini/commands/medical.toml",
        "repo/.gemini/commands/nutritionist.toml",
        "repo/.github",
        "repo/.github/agents",
        "repo/.github/agents/coach.md",
        "repo/.github/agents/course-strategist.md",
        "repo/.github/agents/medical.md",
        "repo/.github/agents/nutritionist.md",
        "repo/.github/skills",
        "repo/.mcp.json",
        "repo/.opencode",
        "repo/.opencode/agents",
        "repo/.opencode/agents/coach.md",
        "repo/.opencode/agents/course-strategist.md",
        "repo/.opencode/agents/medical.md",
        "repo/.opencode/agents/nutritionist.md",
        "repo/.opencode/skills",
        "repo/.windsurf",
        "repo/.windsurf/mcp_config.json",
        "repo/activities",
        "repo/config/workspace.user.toml",
        "repo/config/workspace.user.toml.bak",
        "repo/medical",
        "repo/nutrition",
        "repo/planning",
        "repo/rapports",
        "repo/resources",
    },
    "coach-server": {
        "home/.claude.json",
        "home/.config/ai-running-coach",
        "home/.config/ai-running-coach/workspace",
        "home/Library",
        "home/Library/LaunchAgents",
        "home/Library/LaunchAgents/com.ai-running-coach.daily-sync.plist",
        "home/Library/LaunchAgents/com.ai-running-coach.remote.plist",
        "repo/.claude",
        "repo/.claude/agents",
        "repo/.claude/agents/coach.md",
        "repo/.claude/agents/course-strategist.md",
        "repo/.claude/agents/medical.md",
        "repo/.claude/agents/nutritionist.md",
        "repo/.claude/skills",
        "repo/.mcp.json",
        "repo/activities",
        "repo/config/workspace.user.toml",
        "repo/config/workspace.user.toml.bak",
        "repo/logs",
        "repo/medical",
        "repo/nutrition",
        "repo/planning",
        "repo/rapports",
        "repo/resources",
    },
    "docker": {
        "home/.claude.json",
        "home/.config/ai-running-coach",
        "home/.config/ai-running-coach/workspace",
        "home/Library",
        "home/Library/LaunchAgents",
        "home/Library/LaunchAgents/com.ai-running-coach.daily-sync.plist",
        "repo/.claude",
        "repo/.claude/agents",
        "repo/.claude/agents/coach.md",
        "repo/.claude/agents/course-strategist.md",
        "repo/.claude/agents/medical.md",
        "repo/.claude/agents/nutritionist.md",
        "repo/.claude/skills",
        "repo/.mcp.json",
        "repo/activities",
        "repo/config/workspace.user.toml",
        "repo/config/workspace.user.toml.bak",
        "repo/logs",
        "repo/medical",
        "repo/nutrition",
        "repo/planning",
        "repo/rapports",
        "repo/resources",
    },
}


def _added(before: dict, after: dict) -> set:
    return set(after) - set(before)


class TestPresetDryRun(InstallAsserts):
    """`--dry-run` doit fonctionner pour chaque préréglage, sans rien écrire."""

    def test_dry_run_writes_nothing_per_preset(self):
        for preset in EXPECTED_ADDED_PATHS:
            with self.subTest(preset=preset):
                with Sandbox() as sb:
                    before = sb.tree()
                    proc = sb.install("--preset", preset, "--dry-run", **DARWIN)
                    self.assertSucceeded(proc, f"--preset {preset} --dry-run")
                    self.assertTreeUnchanged(
                        before, sb.tree(), f"--preset {preset} --dry-run a écrit sur le disque"
                    )


class TestPresetRealRunFingerprint(InstallAsserts):
    """Empreinte d'arborescence par préréglage — installation réelle (sandbox)."""

    def test_fingerprint_matches_mapping(self):
        for preset, expected in EXPECTED_ADDED_PATHS.items():
            with self.subTest(preset=preset):
                with Sandbox() as sb:
                    before = sb.tree()
                    proc = sb.install("--preset", preset, **DARWIN)
                    self.assertSucceeded(proc, f"--preset {preset}")
                    added = _added(before, sb.tree())
                    missing = expected - added
                    unexpected = added - expected
                    self.assertFalse(
                        missing or unexpected,
                        f"--preset {preset} : empreinte inattendue\n"
                        f"  manquants : {sorted(missing)}\n"
                        f"  en trop   : {sorted(unexpected)}",
                    )

    def test_laptop_configures_every_ide(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--preset", "laptop", **DARWIN))
            for rel in (".mcp.json", ".cursor/mcp.json", ".windsurf/mcp_config.json"):
                self.assertIsFile(sb.repo / rel)
            self.assertIsFile(sb.home / ".config/opencode/opencode.json")

    def test_coach_server_matches_mobile_doc_steps(self):
        """docs/mobile.md enchaîne --ide claude, --daily-sync puis --remote-control."""
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--preset", "coach-server", **DARWIN))
            self.assertIsFile(sb.repo / ".mcp.json")
            self.assertFalse((sb.repo / ".opencode").exists(), "coach-server ne devrait cibler que Claude Code")
            self.assertIsFile(sb.home / "Library/LaunchAgents/com.ai-running-coach.daily-sync.plist")
            self.assertIsFile(sb.home / "Library/LaunchAgents/com.ai-running-coach.remote.plist")
            self.assertCalled(sb, "uv", "run garmin-mcp-auth")

    def test_docker_skips_interactive_auth_and_remote_control(self):
        """docs/dashboard/docker.md : le conteneur ne parle jamais à Garmin."""
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--preset", "docker", **DARWIN))
            self.assertIsFile(sb.home / "Library/LaunchAgents/com.ai-running-coach.daily-sync.plist")
            self.assertFalse(
                (sb.home / "Library/LaunchAgents/com.ai-running-coach.remote.plist").exists(),
                "docker ne doit pas activer Remote Control",
            )
            self.assertFalse(
                any("garmin-mcp-auth" in args for _, args in sb.stub_calls("uv")),
                "docker : garmin-mcp-auth ne devrait pas tourner (--no-auth composé par le préréglage)",
            )
            self.assertOutputContains(sb.install("--preset", "docker", "--dry-run", **DARWIN), "sautée")


class TestPresetExplicitOverridesWin(InstallAsserts):
    """Une option explicite l'emporte toujours sur le préréglage, quel que soit l'ordre."""

    def test_explicit_daily_sync_wins_after_preset(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--preset", "laptop", "--daily-sync", "--no-auth", **DARWIN))
            self.assertIsFile(sb.home / "Library/LaunchAgents/com.ai-running-coach.daily-sync.plist")

    def test_explicit_daily_sync_wins_before_preset(self):
        """Même résultat en inversant l'ordre : « --daily-sync --preset laptop »."""
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--daily-sync", "--preset", "laptop", "--no-auth", **DARWIN))
            self.assertIsFile(sb.home / "Library/LaunchAgents/com.ai-running-coach.daily-sync.plist")

    def test_explicit_no_auth_wins_after_preset(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--preset", "coach-server", "--no-auth", **DARWIN))
            self.assertFalse(
                any("garmin-mcp-auth" in args for _, args in sb.stub_calls("uv")),
                "garmin-mcp-auth appelé malgré --no-auth explicite (préréglage coach-server)",
            )

    def test_explicit_no_auth_wins_before_preset(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--no-auth", "--preset", "coach-server", **DARWIN))
            self.assertFalse(
                any("garmin-mcp-auth" in args for _, args in sb.stub_calls("uv")),
                "garmin-mcp-auth appelé malgré --no-auth explicite (préréglage coach-server)",
            )

    def test_explicit_ide_wins_over_preset_after(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--preset", "coach-server", "--ide", "all", "--no-auth", **DARWIN))
            self.assertIsFile(sb.repo / ".cursor/mcp.json")

    def test_explicit_ide_wins_over_preset_before(self):
        with Sandbox() as sb:
            self.assertSucceeded(sb.install("--ide", "all", "--preset", "coach-server", "--no-auth", **DARWIN))
            self.assertIsFile(sb.repo / ".cursor/mcp.json")

    def test_recap_marks_explicit_vs_preset_origin(self):
        with Sandbox() as sb:
            proc = sb.install("--preset", "coach-server", "--no-auth", "--dry-run", **DARWIN)
            self.assertSucceeded(proc)
            out = proc.stdout
            self.assertIn("Récapitulatif de la configuration effective", out)
            # Option explicite : marquée comme telle, jamais rattachée au préréglage.
            self.assertIn("explicite", out)
            self.assertIn("préréglage coach-server", out)


class TestUnknownPreset(InstallAsserts):
    def test_unknown_preset_is_a_clean_error(self):
        with Sandbox() as sb:
            proc = sb.install("--preset", "raspberry-pi")
            self.assertFailed(proc, "--preset inconnu")
            self.assertOutputContains(proc, "raspberry-pi")
            for name in ("laptop", "coach-server", "docker"):
                self.assertOutputContains(proc, name)
            self.assertOutputLacks(proc, "unbound variable")

    def test_preset_missing_value_is_a_clean_error(self):
        with Sandbox() as sb:
            proc = sb.install("--preset")
            self.assertFailed(proc, "--preset sans valeur")
            self.assertOutputLacks(proc, "unbound variable")
