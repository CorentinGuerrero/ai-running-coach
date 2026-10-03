"""Palier B — les prompts de la chaleur (#171) passent par le script, jamais par un calcul maison."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

PROMPTS = (
    "agents/coach.md",
    "skills/weather-forecast/SKILL.md",
    "skills/garmin-workout-scheduling/SKILL.md",
    "skills/intervals-icu-best-practices/SKILL.md",
)


class TestHeatPromptsUseTheScript(unittest.TestCase):
    def test_prompts_mention_the_heat_command(self):
        for rel in PROMPTS:
            text = (REPO / rel).read_text(encoding="utf-8")
            self.assertIn("--heat", text, rel)
            self.assertIn("arc_workout_targets.py", text, rel)

    def test_coach_never_in_prompt_arithmetic(self):
        text = (REPO / "agents/coach.md").read_text(encoding="utf-8")
        self.assertIn("never your own arithmetic", text)
        self.assertIn("never keep the intensity at 🔴", text)


if __name__ == "__main__":
    unittest.main()
