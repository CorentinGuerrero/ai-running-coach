"""Palier D — score « Trail Shape » (#63) : formule, cas limites, renormalisation.

Teste `arc_trail_shape.trail_shape_report` directement (dicts en entrée, aucune
base SQLite) — la lecture objectif/activités depuis l'index est couverte à part
par `TestTrailShapeCli` dans `tests/data/test_arc_index.py`.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import arc_trail_shape as TS  # noqa: E402

TODAY = date(2026, 9, 27)


def objective(**overrides) -> dict:
    base = {"name": "Trail des Crêtes", "race_date": "2026-12-06",
            "distance_m": 21100.0, "elevation_gain_m": 1200.0}
    base.update(overrides)
    return base


def run(offset_days: int, distance_m: float, elevation_gain_m: float = 0,
        duration_s: float = 3600, sport: str = "trail") -> dict:
    from datetime import timedelta
    d = TODAY - timedelta(days=offset_days)
    return {"date": d.isoformat(), "sport": sport, "distance_m": distance_m,
            "elevation_gain_m": elevation_gain_m, "duration_s": duration_s}


class TestMissingOrInvalidObjective(unittest.TestCase):
    def test_no_objective_file(self):
        r = TS.trail_shape_report(None, [], TODAY)
        self.assertEqual(r["status"], "no_objective")
        self.assertIsNone(r["score"])
        self.assertTrue(r["notes"])

    def test_objective_without_race_date(self):
        r = TS.trail_shape_report({"distance_m": 20000}, [], TODAY)
        self.assertEqual(r["status"], "no_objective")

    def test_objective_without_distance(self):
        r = TS.trail_shape_report({"race_date": "2026-12-06"}, [], TODAY)
        self.assertEqual(r["status"], "incomplete_objective")
        self.assertIsNone(r["score"])

    def test_race_already_past(self):
        r = TS.trail_shape_report(objective(race_date="2026-01-01"), [], TODAY)
        self.assertEqual(r["status"], "race_past")
        self.assertIsNone(r["score"])

    def test_race_too_short(self):
        r = TS.trail_shape_report(objective(distance_m=3000), [], TODAY)
        self.assertEqual(r["status"], "race_too_short")
        self.assertIsNone(r["score"])


class TestSufficientPreparation(unittest.TestCase):
    """Historique proche des cibles : score élevé, toutes les composantes
    éligibles autres que la durabilité (aucune donnée FIT ici)."""

    def setUp(self):
        self.activities = [
            run(0, 10000, 200), run(7, 12000, 300), run(14, 8000, 150),
            run(21, 18000, 1000, duration_s=9600), run(28, 10000, 200),
            run(35, 14000, 400), run(42, 9000, 150), run(49, 16000, 600),
        ]
        self.report = TS.trail_shape_report(objective(), self.activities, TODAY)

    def test_status_ok_with_a_high_score(self):
        self.assertEqual(self.report["status"], "ok")
        self.assertGreater(self.report["score"], 80)

    def test_weekly_volume_and_longest_run_are_eligible_and_under_the_cap(self):
        by_id = {c["id"]: c for c in self.report["components"]}
        self.assertTrue(by_id["weekly_volume"]["eligible"])
        self.assertLess(by_id["weekly_volume"]["ratio"], 1.0)
        self.assertTrue(by_id["longest_run"]["eligible"])
        self.assertAlmostEqual(by_id["longest_run"]["actual"], 18000.0)

    def test_max_dplus_ratio_is_capped_at_one(self):
        by_id = {c["id"]: c for c in self.report["components"]}
        # D+ max observé (1000 m) dépasse largement la cible (600 m = 1200 * 0.5) :
        # le ratio ne doit JAMAIS dépasser 1.0, quel que soit le dépassement réel.
        self.assertEqual(by_id["max_dplus"]["ratio"], 1.0)

    def test_durability_is_omitted_and_weights_are_renormalized(self):
        by_id = {c["id"]: c for c in self.report["components"]}
        self.assertFalse(by_id["durability"]["eligible"])
        self.assertIsNotNone(by_id["durability"]["reason"])
        eligible = [c for c in self.report["components"] if c["eligible"]]
        total = sum(c["weight_renormalized"] for c in eligible)
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_data_confidence_is_normal_with_a_full_window(self):
        self.assertEqual(self.report["data_confidence"], "normal")
        self.assertEqual(self.report["weeks_with_data"], 8)


class TestInsufficientPreparation(unittest.TestCase):
    """Une seule petite sortie sur la fenêtre : score bas, données éparses."""

    def setUp(self):
        self.activities = [run(2, 6000, 50, duration_s=2000)]
        self.report = TS.trail_shape_report(objective(), self.activities, TODAY)

    def test_status_ok_with_a_low_score(self):
        self.assertEqual(self.report["status"], "ok")
        self.assertLess(self.report["score"], 30)

    def test_low_data_confidence_is_flagged(self):
        self.assertEqual(self.report["data_confidence"], "low")
        self.assertEqual(self.report["weeks_with_data"], 1)
        self.assertTrue(any("semaine" in n for n in self.report["notes"]))

    def test_durability_omitted_no_long_run_at_all(self):
        by_id = {c["id"]: c for c in self.report["components"]}
        self.assertFalse(by_id["durability"]["eligible"])


class TestRoadObjectiveWithoutElevation(unittest.TestCase):
    """Objectif route sans D+ renseigné (`elevation_gain_m` absent) : la
    composante D+ max est omise structurellement, jamais notée à 0."""

    def test_max_dplus_component_is_omitted(self):
        obj = objective(elevation_gain_m=None)
        activities = [run(i * 7, 12000, 0) for i in range(6)]
        r = TS.trail_shape_report(obj, activities, TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertFalse(by_id["max_dplus"]["eligible"])
        self.assertIn("route", by_id["max_dplus"]["reason"])
        eligible_ids = {c["id"] for c in r["components"] if c["eligible"]}
        self.assertNotIn("max_dplus", eligible_ids)


class TestFarHorizon(unittest.TestCase):
    def test_note_is_added_beyond_the_far_horizon_but_score_still_computes(self):
        obj = objective(race_date="2028-06-15")
        activities = [run(i * 7, 12000, 200) for i in range(8)]
        r = TS.trail_shape_report(obj, activities, TODAY)
        self.assertEqual(r["status"], "ok")
        self.assertIsNotNone(r["score"])
        self.assertTrue(any("semaines" in n and "commenc" in n for n in r["notes"]))


class TestDurabilityComponent(unittest.TestCase):
    """La composante durabilité (#48) s'intègre au score dès qu'une sortie
    longue de la fenêtre porte un fade GAP déjà dérivé (jamais recalculé ici,
    voir `arc_metrics.durability_trend` — ce module ne fait que consommer)."""

    def test_measured_fade_produces_an_eligible_component(self):
        act = run(10, 20000, 500, duration_s=9000)
        act["durability_gap_fade_pct"] = 5.0
        obj = objective()
        r = TS.trail_shape_report(obj, [act], TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertTrue(by_id["durability"]["eligible"])
        self.assertAlmostEqual(by_id["durability"]["actual"], 5.0)
        # fade 5 % sur un plafond de 15 % (DURABILITY_MAX_ACCEPTABLE_FADE_PCT) -> ratio 2/3.
        self.assertAlmostEqual(by_id["durability"]["ratio"], 1 - 5.0 / TS.DURABILITY_MAX_ACCEPTABLE_FADE_PCT, places=3)

    def test_large_fade_floors_the_ratio_at_zero(self):
        act = run(10, 20000, 500, duration_s=9000)
        act["durability_gap_fade_pct"] = 90.0
        r = TS.trail_shape_report(objective(), [act], TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertEqual(by_id["durability"]["ratio"], 0.0)


class TestWeightsSumToOne(unittest.TestCase):
    def test_component_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(TS.COMPONENT_WEIGHTS.values()), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
