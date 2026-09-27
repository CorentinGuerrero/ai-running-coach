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
        install_sh = (REPO / "install.sh").read_text(encoding="utf-8")
        self.assertIn("--source", install_sh)
        self.assertIn("garmin|intervals", install_sh)
        self.assertIn("install_intervals_mcp", install_sh)


if __name__ == "__main__":
    unittest.main()
