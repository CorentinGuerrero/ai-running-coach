"""Palier D — `scripts/arc_log.py` : arithmétique et correspondance catalogue pour `/log` (#67).

Le LLM ne fait que l'extraction d'entités (quel produit, quelle quantité, quelle
douleur...) ; toute la conversion catalogue et les sommes sont ici, en pur
stdlib, pour être exactes et testables sans jamais invoquer de modèle.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import arc_guardrails  # noqa: E402
import arc_log as L  # noqa: E402

CATALOGUE_MD = """
# Catalogue produits — test

| Produit | Portion | Glucides |
|---|---|---|
| Gel Fixture Test | 1 sachet (40 g) | 32 g |
| Barre Fixture Energie | 1 barre (50 g) | 28 g |
| Barre Fixture Recup | 1 barre (60 g) | 20 g |
"""


class TestNormalizeAndParsing(unittest.TestCase):
    def test_normalize_name_strips_accents_and_case(self):
        self.assertEqual(L.normalize_name("Gel Énergétique"), "gel energetique")

    def test_parse_quantity_accepts_comma_decimal(self):
        self.assertEqual(L.parse_quantity("2"), 2.0)
        self.assertEqual(L.parse_quantity("0,5"), 0.5)
        self.assertEqual(L.parse_quantity(3), 3.0)

    def test_parse_quantity_rejects_garbage(self):
        with self.assertRaises(L.ArcLogError):
            L.parse_quantity("beaucoup")

    def test_parse_volume_ml_plain_ml(self):
        self.assertEqual(L.parse_volume_ml("500 ml"), 500.0)
        self.assertEqual(L.parse_volume_ml("750ml"), 750.0)

    def test_parse_volume_ml_liters_comma_decimal(self):
        self.assertEqual(L.parse_volume_ml("0,5 l"), 500.0)
        self.assertEqual(L.parse_volume_ml("1l"), 1000.0)
        self.assertEqual(L.parse_volume_ml("1,5 litres"), 1500.0)

    def test_parse_volume_ml_bare_number_is_millilitres(self):
        self.assertEqual(L.parse_volume_ml(500), 500.0)
        self.assertEqual(L.parse_volume_ml("500"), 500.0)


class TestCatalogueParsing(unittest.TestCase):
    def test_parse_catalogue_extracts_name_and_carbs(self):
        products = L.parse_catalogue(CATALOGUE_MD)
        names = {p["name"]: p["carbs_g"] for p in products}
        self.assertEqual(names["Gel Fixture Test"], 32.0)
        self.assertEqual(names["Barre Fixture Energie"], 28.0)
        self.assertEqual(len(products), 3)

    def test_parse_catalogue_ignores_rows_without_carbs_number(self):
        text = "| Produit | Portion | Glucides |\n|---|---|---|\n| Mystère | ras | à préciser |\n"
        self.assertEqual(L.parse_catalogue(text), [])


class TestProductMatching(unittest.TestCase):
    def setUp(self):
        self.catalogue = L.parse_catalogue(CATALOGUE_MD)

    def test_exact_match_case_and_accent_insensitive(self):
        status, product = L.match_product("gel fixture test", self.catalogue)
        self.assertEqual(status, "matched")
        self.assertEqual(product["name"], "Gel Fixture Test")

    def test_plural_matches_singular_catalogue_entry(self):
        status, product = L.match_product("Gels Fixture Test", self.catalogue)
        self.assertEqual(status, "matched")
        self.assertEqual(product["name"], "Gel Fixture Test")

    def test_partial_word_match_single_candidate(self):
        status, product = L.match_product("gel", self.catalogue)
        self.assertEqual(status, "matched")
        self.assertEqual(product["name"], "Gel Fixture Test")

    def test_ambiguous_partial_match_returns_all_candidates(self):
        status, candidates = L.match_product("barre", self.catalogue)
        self.assertEqual(status, "ambiguous")
        self.assertEqual(candidates, ["Barre Fixture Energie", "Barre Fixture Recup"])

    def test_unknown_product_not_in_catalogue(self):
        status, result = L.match_product("pate de fruit", self.catalogue)
        self.assertEqual(status, "unknown")
        self.assertIsNone(result)

    def test_unknown_when_catalogue_empty(self):
        status, result = L.match_product("gel", [])
        self.assertEqual(status, "unknown")
        self.assertIsNone(result)


class TestComputeNutrition(unittest.TestCase):
    def setUp(self):
        self.catalogue = L.parse_catalogue(CATALOGUE_MD)

    def test_sums_carbs_for_multiple_matched_items(self):
        items = [{"product": "gels", "qty": "2"}, {"product": "Barre Fixture Energie", "qty": 1}]
        result = L.compute_nutrition(items, self.catalogue)
        self.assertEqual(result["carbs_g"], 32.0 * 2 + 28.0)
        self.assertEqual(len(result["matched"]), 2)
        self.assertEqual(result["unknown"], [])
        self.assertEqual(result["ambiguous"], [])

    def test_unknown_product_never_invents_carbs(self):
        items = [{"product": "pate de fruit maison", "qty": "1"}]
        result = L.compute_nutrition(items, self.catalogue)
        self.assertIsNone(result["carbs_g"])
        self.assertEqual(len(result["unknown"]), 1)
        self.assertEqual(result["unknown"][0]["reason"], "unknown_product")

    def test_ambiguous_product_never_invents_carbs(self):
        items = [{"product": "barre", "qty": "1"}]
        result = L.compute_nutrition(items, self.catalogue)
        self.assertIsNone(result["carbs_g"])
        self.assertEqual(len(result["ambiguous"]), 1)
        self.assertEqual(
            result["ambiguous"][0]["candidates"],
            ["Barre Fixture Energie", "Barre Fixture Recup"],
        )

    def test_no_catalogue_marks_items_unknown_with_reason(self):
        result = L.compute_nutrition([{"product": "gel", "qty": "1"}], [])
        self.assertIsNone(result["carbs_g"])
        self.assertEqual(result["unknown"][0]["reason"], "no_catalogue")


class TestComputeFluids(unittest.TestCase):
    def test_sums_mixed_units(self):
        self.assertEqual(L.compute_fluids(["500 ml", "0,5 l"]), 1000.0)

    def test_empty_returns_none(self):
        self.assertIsNone(L.compute_fluids([]))


class TestComputePain(unittest.TestCase):
    def test_flags_consult_at_or_above_threshold(self):
        entries = L.compute_pain(
            [{"location": "genou gauche", "score": "7"}, {"location": "mollet", "score": "3"}],
            threshold=7.0,
        )
        self.assertTrue(entries[0]["consult"])
        self.assertFalse(entries[1]["consult"])

    def test_threshold_matches_arc_guardrails_constant(self):
        """Verrou anti-dérive : `arc_log` ne réimplémente pas le seuil sans le
        garder synchronisé avec `arc_guardrails.PAIN_CONSULT_THRESHOLD` (#57)."""
        self.assertEqual(L.PAIN_CONSULT_THRESHOLD, arc_guardrails.PAIN_CONSULT_THRESHOLD)


class TestProcessEndToEnd(unittest.TestCase):
    def test_full_payload(self):
        payload = {
            "catalogue_paths": [],
            "nutrition_items": [{"product": "gel", "qty": "2"}],
            "fluid_entries": ["500 ml"],
            "pain": [{"location": "genou gauche", "score": "3"}],
            "rpe": "7",
            "position": "km 15",
        }
        # Catalogue vide explicite (liste []) → produit inconnu, jamais deviné.
        result = L.process(payload)
        self.assertEqual(result["nutrition"]["unknown"][0]["reason"], "no_catalogue")
        self.assertEqual(result["fluid_intake_ml"], 500.0)
        self.assertEqual(result["pain"][0]["consult"], False)
        self.assertEqual(result["rpe"], 7.0)
        self.assertEqual(result["position"], "km 15")

    def test_rpe_out_of_range_is_warned_not_rejected(self):
        result = L.process({"rpe": "12"})
        self.assertEqual(result["rpe"], 12.0)
        self.assertTrue(any("rpe" in w for w in result["warnings"]))

    def test_many_pain_entries_warns_like_contract(self):
        pain = [{"location": f"zone {i}", "score": "2"} for i in range(11)]
        result = L.process({"pain": pain})
        self.assertTrue(any("pain" in w for w in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
