"""Palier B — parité de comportement Garmin quand `[data].source = "garmin"` (#68).

Critère d'acceptation de la story : aucun comportement Garmin modifié quand la
source reste `garmin` (le défaut). Comme les prompts des agents sont le
comportement (ce sont les seules instructions que l'agent suit), on ne peut
pas comparer un "avant/après" binaire une fois la story mergée — ce test
verrouille à la place un jeu de phrases Garmin **load-bearing**, prises mot
pour mot dans `agents/coach.md`/`agents/medical.md` AVANT #68, et vérifie
qu'elles existent encore, verbatim, après l'ajout de la section « DATA SOURCE
MANDATE ». Un futur changement qui les modifierait devra mettre à jour cette
liste consciemment, jamais par accident au détour d'un ajout intervals.icu.

Complète (ne remplace pas) les cas d'éval existants (`health-full-triad`,
`daily-sync-resume-block`, ...) : ceux-ci exercent le comportement à
l'exécution (palier C) quand `ARC_LLM_TESTS=1` ; celui-ci verrouille le texte
source, gratuitement, à chaque run du palier B.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
COACH = (REPO / "agents/coach.md").read_text(encoding="utf-8")
MEDICAL = (REPO / "agents/medical.md").read_text(encoding="utf-8")
AGENTS_MD = (REPO / "AGENTS.md").read_text(encoding="utf-8")
DAILY_SYNC_SKILL = (REPO / "skills/garmin-daily-sync/SKILL.md").read_text(encoding="utf-8")
DAILY_SYNC_SH = (REPO / "scripts/daily-sync.sh").read_text(encoding="utf-8")
INSTALL_SH = (REPO / "install.sh").read_text(encoding="utf-8")

# Phrases Garmin-mode telles qu'écrites avant #68 — copiées verbatim depuis
# `agents/coach.md`/`agents/medical.md` (git blame antérieur à cette story).
COACH_GARMIN_SENTENCES = [
    "you MUST fetch and report ALL THREE of: overnight HRV (`get_hrv_data`), "
    "**resting heart rate (`get_rhr_day`)**, and training readiness (`get_training_readiness`)",
    "`get_rhr_day(date)` returns it directly. Do NOT fall back to `get_sleep_data`",
    "push the planned sessions DIRECTLY to the Garmin Connect calendar via the "
    "`schedule_workouts` tool",
    "**Push:** Use `schedule_workouts` with `{calendar_date, workout_data}` per session.",
    "**JSON schema:** See the `garmin-workout-scheduling` skill. Never use "
    "`steps`/`conditionValue` (400 error); use `workoutSegments`/`workoutSteps`/`endConditionValue`.",
]

MEDICAL_GARMIN_SENTENCES = [
    "Any availability decision MUST be based on all three — overnight HRV "
    "(`get_hrv_data`), **resting heart rate (`get_rhr_day`)** and training readiness "
    "(`get_training_readiness`)",
    "Use `get_rhr_day` — never pull `get_sleep_data` (>400 KB) just to read resting HR.",
]

# Idem pour skills/garmin-daily-sync/SKILL.md.
DAILY_SYNC_GARMIN_SENTENCES = [
    "fetch from the `garmin` MCP\n   > server: activities (with splits and `recovery_hr_bpm`), "
    "sleep, HRV, training readiness,",
]

# Idem pour AGENTS.md — la règle "secondaire sinon" doit rester la règle par
# défaut (source garmin, jamais configurée) : c'est la phrase qui dit que rien
# n'installe/n'active intervals.icu sans que l'athlète l'ait demandé.
AGENTS_MD_GARMIN_SENTENCES = [
    "**SECONDAIRE sinon** (défaut) : uniquement si l'utilisateur le demande "
    "explicitement (skill `intervals-icu-best-practices`), serveur non installé "
    "par `install.sh`, configuration manuelle (`docs/faq.md`).",
]


class TestGarminModeTextUnchanged(unittest.TestCase):
    def test_coach_garmin_sentences_still_present_verbatim(self):
        missing = [s for s in COACH_GARMIN_SENTENCES if s not in COACH]
        self.assertFalse(
            missing,
            "agents/coach.md : phrase(s) Garmin-mode modifiée(s) ou supprimée(s) — "
            "vérifier qu'aucun comportement source=garmin n'a changé (#68) :\n  "
            + "\n  ".join(missing),
        )

    def test_medical_garmin_sentences_still_present_verbatim(self):
        missing = [s for s in MEDICAL_GARMIN_SENTENCES if s not in MEDICAL]
        self.assertFalse(
            missing,
            "agents/medical.md : phrase(s) Garmin-mode modifiée(s) ou supprimée(s) — "
            "vérifier qu'aucun comportement source=garmin n'a changé (#68) :\n  "
            + "\n  ".join(missing),
        )

    def test_daily_sync_skill_garmin_sentences_still_present_verbatim(self):
        missing = [s for s in DAILY_SYNC_GARMIN_SENTENCES if s not in DAILY_SYNC_SKILL]
        self.assertFalse(
            missing,
            "skills/garmin-daily-sync/SKILL.md : phrase(s) Garmin-mode modifiée(s) — "
            "vérifier qu'aucun comportement source=garmin n'a changé (#68) :\n  "
            + "\n  ".join(missing),
        )

    def test_agents_md_secondary_rule_still_present_verbatim(self):
        missing = [s for s in AGENTS_MD_GARMIN_SENTENCES if s not in AGENTS_MD]
        self.assertFalse(
            missing,
            "AGENTS.md : la règle « secondaire sinon » a changé — intervals.icu ne "
            "doit jamais devenir actif sans que [data].source = \"intervals\" soit "
            "explicitement configuré (#68) :\n  " + "\n  ".join(missing),
        )


class TestDataSourceDocumented(unittest.TestCase):
    """Le nouveau comportement (#68) est bien documenté là où un agent le lit."""

    def test_agents_and_skill_mention_data_source_mandate(self):
        for path, text in (("agents/coach.md", COACH), ("agents/medical.md", MEDICAL)):
            with self.subTest(path=path):
                self.assertIn("[data].source", text)
                self.assertIn("DATA SOURCE MANDATE", text)

    def test_agents_md_documents_the_tool_mapping_and_degraded_features(self):
        self.assertIn("[data].source", AGENTS_MD)
        for tool in (
            "get_wellness_for_date", "get_recent_activities", "get_activity_details",
            "create_event", "bulk_create_events",
        ):
            self.assertIn(tool, AGENTS_MD)
        # La readiness algorithmique Garmin n'a pas d'équivalent : ne jamais
        # laisser cette exception disparaître silencieusement d'un futur edit.
        self.assertIn("aucun équivalent", AGENTS_MD)
        self.assertIn("Téléchargement FIT", AGENTS_MD)
        self.assertIn("Upload de parcours", AGENTS_MD)

    def test_config_workspace_toml_declares_the_key_and_default(self):
        toml_text = (REPO / "config/workspace.toml").read_text(encoding="utf-8")
        self.assertIn("[data]", toml_text)
        self.assertIn('source = "garmin"', toml_text)

    def test_install_sh_exposes_source_flag_for_both_values(self):
        self.assertIn("--source", INSTALL_SH)
        self.assertIn("garmin|intervals", INSTALL_SH)
        self.assertIn("install_intervals_mcp", INSTALL_SH)

    def test_install_sh_only_persists_source_when_explicit(self):
        """Une installation Garmin par défaut ne doit JAMAIS écrire [data] dans
        workspace.user.toml (revue PR #116, blocker 2) — sinon un simple
        `./install.sh` diffère de main pour tout le monde."""
        self.assertIn('[[ "$EXPLICIT_SOURCE" -eq 1 ]] || return 0', INSTALL_SH)

    def test_install_sh_resolves_source_from_existing_config(self):
        """Un rerun sans --source ne doit jamais faire revenir un athlète
        intervals.icu vers garmin (revue PR #116, blocker 2)."""
        self.assertIn("resolve_source", INSTALL_SH)
        self.assertIn("--section data --key source --default garmin", INSTALL_SH)

    def test_install_sh_never_puts_credentials_in_mcp_env_block(self):
        """Ni .env (introuvable au démarrage du serveur par l'IDE) ni ${VAR}
        (jamais exporté, jamais interpolé par tous les IDE) — voir
        write_intervals_wrapper() (revue PR #116, blocker 1). La chaîne
        `INTERVALS_ICU_API_KEY` reste CITÉE en commentaire (pour expliquer
        pourquoi elle est évitée) : seul le corps réel des deux fonctions qui
        construisent la config MCP ne doit plus jamais l'injecter dans un
        `printf`."""
        import re

        for fn in ("mcp_server_value_intervals", "mcp_server_value_intervals_opencode"):
            match = re.search(rf"^{fn}\(\) \{{(.*?)^\}}", INSTALL_SH, re.MULTILINE | re.DOTALL)
            self.assertIsNotNone(match, f"fonction {fn}() introuvable dans install.sh")
            body = match.group(1)
            for line in body.splitlines():
                if line.strip().startswith("printf"):
                    self.assertNotIn("INTERVALS_ICU_API_KEY", line, f"{fn}() : secret dans le printf JSON")
        self.assertIn("write_intervals_wrapper", INSTALL_SH)
        self.assertIn("INTERVALS_ENV_DIR/run.sh", INSTALL_SH)

    def test_install_sh_pins_the_intervals_server_commit(self):
        self.assertIn("INTERVALS_MCP_REF=", INSTALL_SH)
        self.assertIn("@cb91d4a", INSTALL_SH)

    def test_daily_sync_skips_garmin_token_checks_in_intervals_mode(self):
        """check_token_alert() ne doit jamais tourner sous source=intervals —
        intervals-icu-mcp n'a pas d'échéance de token OAuth comparable, et
        `coach_doctor.py --check garmin_token` n'a rien à y lire (revue PR #116,
        blocker 3)."""
        self.assertIn('[[ "$SOURCE" == "garmin" ]] || return 0', DAILY_SYNC_SH)
        self.assertIn('SOURCE="$(toml_get data source garmin)"', DAILY_SYNC_SH)



if __name__ == "__main__":
    unittest.main()
