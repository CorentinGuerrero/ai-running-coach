"""Palier B — foulée (#151) : la synthèse reste un INDICE (jamais un diagnostic), ne parle jamais de
changer la charge ou le plan, et le rappel « indice, pas diagnostic » figure une seule fois par carte
d'inspections. Lint de texte pur : aucun modèle, aucun serveur.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import arc_gait as GT  # noqa: E402
import arc_metrics as M  # noqa: E402

APP_JS = (REPO / "web/js/app.js").read_text(encoding="utf-8")
VIEWS = (REPO / "docs/dashboard/views.md").read_text(encoding="utf-8")

# Verbe de modification de charge/plan + son objet : interdit dans toute surface « Foulée » — sauf négation
# explicite (« ne modifie ni la charge ni le plan »), retirée avant la recherche.
LOAD_CHANGE = re.compile(
    r"(réduis|réduire|diminu|augmente|augmenter|allège|alléger|allègement|baisse|baisser|ajuste|ajuster|"
    r"modifie|modifier|adapte|adapter|change|changer|lève le pied)[a-zé]*\s+(?:ta |votre |la |le |les )?"
    r"(charge|volume|plan|entraînement|séance)", re.I)
NEGATION = re.compile(r"ne modifie ni la charge ni le plan d'entraînement|sans effet sur la charge ni le plan", re.I)


def gait_card_source() -> str:
    start = APP_JS.index("const NB = ")
    end = APP_JS.index("// Vue : Santé")
    return APP_JS[start:end]


def foulee_docs() -> str:
    start = VIEWS.index("### Foulée")
    end = VIEWS.index("## Semaine", start)
    return VIEWS[start:end]


def strip_negations(text: str) -> str:
    return NEGATION.sub("", text)


class TestGaitWording(unittest.TestCase):
    def surfaces(self):
        yield "arc_gait.CAVEAT", GT.CAVEAT
        for key, text in GT.ASSUMPTIONS.items():
            yield f"arc_gait.ASSUMPTIONS[{key}]", text
        yield "arc_metrics.ASSUMPTIONS[gait]", M.ASSUMPTIONS["gait"]
        yield "web/js/app.js (carte Foulée)", gait_card_source()
        yield "docs/dashboard/views.md (Foulée)", foulee_docs()

    def test_no_load_or_plan_change_wording(self):
        for name, text in self.surfaces():
            hit = LOAD_CHANGE.search(strip_negations(text))
            self.assertIsNone(hit, f"{name} : formulation de modification de charge/plan « {hit and hit.group(0)} »")

    def test_the_lint_itself_catches_load_change_wording(self):
        for bad in ("Réduisez la charge.", "il faut alléger le volume", "adaptez votre plan", "Modifiez le plan"):
            self.assertIsNotNone(LOAD_CHANGE.search(strip_negations(bad)), bad)
        self.assertIsNone(LOAD_CHANGE.search(strip_negations(GT.CAVEAT)))

    def test_contradiction_messages_carry_no_load_change_wording(self):
        dynamics = {"stance_balance_pct": GT.metric_trend(
            "stance_balance_pct", [(f"2026-09-{i:02d}", 50.2) for i in range(1, 9)], __import__("datetime").date(2026, 9, 23))}
        insp = GT.inspection_gait([
            {"gear_id": "a", "date": "2026-09-01", "gait_hints": ["heel_strike"], "asymmetry": {"level": "mild", "side": "left"}},
            {"gear_id": "b", "date": "2026-09-02", "gait_hints": ["midfoot_forefoot_strike"]}])
        messages = [c["message"] for c in GT.find_contradictions(dynamics, insp)]
        self.assertGreaterEqual(len(messages), 2)
        for m in messages:
            self.assertIsNone(LOAD_CHANGE.search(m), m)

    def test_caveat_is_present_everywhere_it_must_be(self):
        self.assertIn("Indice, jamais un diagnostic", GT.CAVEAT)
        self.assertIn("ne modifie ni la charge ni le plan", GT.CAVEAT)
        self.assertIn("jamais un diagnostic", gait_card_source())
        self.assertIn("jamais un diagnostic", foulee_docs().lower())
        self.assertIn("jamais un diagnostic", M.ASSUMPTIONS["gait"].lower())

    def test_balance_side_is_declared_unverified(self):
        self.assertIn("pas établi", foulee_docs())
        self.assertIn("n'est pas établi", GT.ASSUMPTIONS["balance_side"])
        self.assertIn("approximation du projet", foulee_docs())


class TestInspectionCaveatOncePerCard(unittest.TestCase):
    def function_body(self, name: str) -> str:
        start = APP_JS.index(f"function {name}(")
        depth, i = 0, APP_JS.index("{", start)
        begin = i
        while True:
            depth += {"{": 1, "}": -1}.get(APP_JS[i], 0)
            if depth == 0:
                return APP_JS[begin:i + 1]
            i += 1

    def test_per_inspection_rendering_has_no_caveat(self):
        body = self.function_body("inspectionItem")
        self.assertNotRegex(body, r"diagnostic|INSPECTION_CAVEAT")

    def test_each_card_shows_it_once(self):
        for card in ("gearInspectionSection", "gearShoeDetail"):
            body = self.function_body(card)
            expected = 2 if card == "gearShoeDetail" else 1      # fiche : carte « ignorée » ET carte normale
            self.assertEqual(body.count("INSPECTION_CAVEAT"), expected, card)

    def test_caveat_defined_once_and_links_to_the_gait_card(self):
        self.assertEqual(len(re.findall(r"const INSPECTION_CAVEAT", APP_JS)), 1)
        self.assertIn("pas un diagnostic", APP_JS)
        self.assertIn("#/sante?section=foulee", APP_JS)


class TestDocsReferences(unittest.TestCase):
    def test_views_documents_the_card_and_its_screenshot(self):
        self.assertIn("### Foulée", VIEWS)
        self.assertIn("../assets/dashboard/sante-foulee.webp", VIEWS)
        self.assertIn("gait-summary", foulee_docs())
        self.assertIn("--refresh-dynamics", foulee_docs())


if __name__ == "__main__":
    unittest.main()
