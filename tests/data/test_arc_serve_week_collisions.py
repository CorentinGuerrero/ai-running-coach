"""Palier D — `/api/summary` (#69, revue de code) : une collision de semaine
(fichier VALIDE au contrat, une entrée éclipsée par un autre fichier) ne doit
JAMAIS compter dans `incomplete_files` (« N fichier(s) hors contrat ») — elle
est comptée à part, `week_collisions_count`.

Workspace minimal écrit à la main (fichiers ```arc, pas de sous-processus) —
même approche que `tests/data/test_arc_serve_gear.py`.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import arc_serve as S  # noqa: E402


def arc(kind_line: str) -> str:
    return f"# Titre\n\n```arc\n{kind_line}\n```\n\nTexte.\n"


class TestSummaryWeekCollisions(unittest.TestCase):
    TODAY = "2026-09-23"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="arc-week-collisions-"))
        self.ws = self.tmp / "ws"
        for d in ("activities", "medical", "nutrition", "planning", "rapports"):
            (self.ws / d).mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel: str, text: str) -> None:
        (self.ws / rel).write_text(text, encoding="utf-8")

    def summary(self) -> dict:
        store = S.Store(self.ws, memory=True, today=self.TODAY)
        return S.api_summary(store, {})

    def test_no_collision_gives_zero_of_both_counts(self):
        s = self.summary()
        self.assertEqual(s["incomplete_files"], 0)
        self.assertEqual(s["week_collisions_count"], 0)

    def test_genuinely_off_contract_file_counts_as_incomplete_not_collision(self):
        self.write("medical/2026-09-20_health.md", "# Santé\n\nPas de bloc.\n")
        s = self.summary()
        self.assertEqual(s["incomplete_files"], 1)
        self.assertEqual(s["week_collisions_count"], 0)

    def test_week_collision_counts_as_collision_not_incomplete(self):
        """Le coeur du bug (#69, revue de code) : un fichier plan multi-semaines
        déjà valide au contrat, dont une entrée est éclipsée par le fichier
        dédié de la même semaine, ne doit jamais gonfler `incomplete_files`
        (« hors contrat ») — il est déjà PARFAITEMENT au contrat."""
        self.write("planning/Semaine_2026-09-14.md", arc(json.dumps({
            "arc": 1, "kind": "week", "weeks": [
                {"week_start": "2026-09-14", "location": "Tournai", "sessions": []},
                {"week_start": "2026-09-21", "location": "Tournai", "sessions": []},
            ],
        })))
        self.write("planning/Semaine_2026-09-21.md", arc(json.dumps({
            "arc": 1, "kind": "week", "week_start": "2026-09-21",
            "location": "Tournai", "sessions": [],
        })))
        s = self.summary()
        self.assertEqual(s["incomplete_files"], 0)
        self.assertEqual(s["week_collisions_count"], 1)

    def test_both_kinds_of_debt_counted_independently(self):
        self.write("medical/2026-09-20_health.md", "# Santé\n\nPas de bloc.\n")
        self.write("planning/Semaine_2026-09-14.md", arc(json.dumps({
            "arc": 1, "kind": "week", "weeks": [
                {"week_start": "2026-09-14", "location": "Tournai", "sessions": []},
                {"week_start": "2026-09-21", "location": "Tournai", "sessions": []},
            ],
        })))
        self.write("planning/Semaine_2026-09-21.md", arc(json.dumps({
            "arc": 1, "kind": "week", "week_start": "2026-09-21",
            "location": "Tournai", "sessions": [],
        })))
        s = self.summary()
        self.assertEqual(s["incomplete_files"], 1)
        self.assertEqual(s["week_collisions_count"], 1)


if __name__ == "__main__":
    unittest.main()
