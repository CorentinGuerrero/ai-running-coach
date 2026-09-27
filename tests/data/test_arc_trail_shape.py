"""Palier D — score « Trail Shape » (#63) : formule, cas limites, renormalisation.

Teste `arc_trail_shape.trail_shape_report` directement (dicts en entrée, aucune
base SQLite) — la lecture objectif/activités depuis l'index est couverte à part
par `TestTrailShapeCli` dans `tests/data/test_arc_index.py`.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
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
    d = TODAY - timedelta(days=offset_days)
    return {"date": d.isoformat(), "sport": sport, "distance_m": distance_m,
            "elevation_gain_m": elevation_gain_m, "duration_s": duration_s}


def note_codes(report: dict) -> set:
    return {n["code"] for n in report["notes"]}


def note_message(report: dict, code: str):
    return next((n["message"] for n in report["notes"] if n["code"] == code), None)


class TestMissingOrInvalidObjective(unittest.TestCase):
    def test_no_objective_file(self):
        r = TS.trail_shape_report(None, [], TODAY)
        self.assertEqual(r["status"], "no_objective")
        self.assertIsNone(r["score"])
        self.assertEqual(note_codes(r), {"no_objective"})

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


class TestWeeklyVolumeTargetCurve(unittest.TestCase):
    """#63 revue de code (blocage 5) : cible sous-linéaire, jamais une simple
    proportion de l'effort de course (triviale pour une course courte,
    irréaliste pour un ultra) — plancher et plafond documentés."""

    def target_for(self, distance_m, elevation_gain_m=0):
        effort_km = TS._race_effort_km(distance_m, elevation_gain_m)
        return TS.weekly_volume_target_km(effort_km)

    def test_10km_is_not_trivial(self):
        # Une proportion linéaire (ex. 50 % de l'effort) donnerait 5 km/semaine
        # pour un 10 km — trivialement atteint par n'importe quel coureur actif.
        target = self.target_for(10000)
        self.assertGreater(target, 15.0)
        self.assertLess(target, TS.WEEKLY_VOLUME_CAP_KM)

    def test_half_marathon_is_between_10k_and_marathon(self):
        t10 = self.target_for(10000)
        thalf = self.target_for(21097.5)
        tmarathon = self.target_for(42195)
        self.assertLess(t10, thalf)
        self.assertLess(thalf, tmarathon)

    def test_marathon_target_is_moderate(self):
        target = self.target_for(42195)
        self.assertGreater(target, 30.0)
        self.assertLess(target, TS.WEEKLY_VOLUME_CAP_KM)

    def test_trail_42km_with_2500_dplus_target_is_higher_than_flat_marathon(self):
        flat = self.target_for(42195)
        trail = self.target_for(42195, 2500)
        self.assertGreater(trail, flat)

    def test_80km_4500_dplus_is_capped_not_elite_level(self):
        # Une proportion linéaire (50 % de l'effort ITRA, ~125 km-effort) exigerait
        # ~62-135 km-effort/semaine selon le ratio choisi — niveau élite. La courbe
        # sous-linéaire, plafonnée, ne doit jamais monter jusque-là.
        target = self.target_for(80000, 4500)
        self.assertLessEqual(target, TS.WEEKLY_VOLUME_CAP_KM)
        self.assertGreater(target, TS.WEEKLY_VOLUME_CAP_KM * 0.8)

    def test_170km_10000_dplus_is_capped_at_the_ceiling(self):
        target = self.target_for(170000, 10000)
        self.assertEqual(target, TS.WEEKLY_VOLUME_CAP_KM)

    def test_very_short_effort_hits_the_floor(self):
        target = TS.weekly_volume_target_km(1.0)
        self.assertEqual(target, TS.WEEKLY_VOLUME_FLOOR_KM)

    def test_zero_effort_returns_the_floor(self):
        self.assertEqual(TS.weekly_volume_target_km(0), TS.WEEKLY_VOLUME_FLOOR_KM)


class TestLongestRunTargetCurve(unittest.TestCase):
    """#63 revue de code (blocage 2) : cible continue en distance de course —
    plus de saut brutal au seuil marathon."""

    def test_42_and_43_km_give_the_same_capped_target(self):
        # L'ancienne formule sautait de "distance elle-même" (42,195 km) à 60 %
        # de la distance (~25,8 km) pour 1 m de plus — désormais continu : les
        # deux distances tombent sur le même plancher (30 km).
        t42 = TS.longest_run_target_m(42000)
        t43 = TS.longest_run_target_m(43000)
        self.assertEqual(t42, TS.LONG_RUN_TARGET_FLOOR_M)
        self.assertEqual(t43, TS.LONG_RUN_TARGET_FLOOR_M)

    def test_road_marathon_targets_30km(self):
        self.assertEqual(TS.longest_run_target_m(42195), 30000.0)

    def test_10km_targets_the_full_distance(self):
        self.assertEqual(TS.longest_run_target_m(10000), 10000.0)

    def test_170km_targets_the_60km_cap(self):
        self.assertEqual(TS.longest_run_target_m(170000), TS.LONG_RUN_TARGET_CAP_M)

    def test_half_marathon_targets_the_full_distance(self):
        # Sous le plancher (30 km), la cible reste la distance elle-même —
        # courir la distance de course en entraînement reste courant jusque-là.
        self.assertEqual(TS.longest_run_target_m(21097.5), 21097.5)


class TestMaxDplusTarget(unittest.TestCase):
    def test_capped_for_a_very_high_elevation_objective(self):
        obj = objective(distance_m=170000, elevation_gain_m=10000)
        activities = [run(i * 7, 12000, 2600, sport="hiking") for i in range(6)]
        r = TS.trail_shape_report(obj, activities, TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertEqual(by_id["max_dplus"]["target"], TS.MAX_DPLUS_TARGET_CAP_M)

    def test_not_capped_below_the_ceiling(self):
        obj = objective(distance_m=21100, elevation_gain_m=1200)
        activities = [run(0, 10000, 400)]
        r = TS.trail_shape_report(obj, activities, TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertEqual(by_id["max_dplus"]["target"], 600.0)


class TestSufficientPreparation(unittest.TestCase):
    """Historique proche des cibles historiques du projet : composantes
    éligibles (hors durabilité, aucune donnée FIT ici) avec des ratios non
    nuls, dont la plus longue sortie et le D+ max nettement couverts — mais le
    volume hebdomadaire, avec la cible sous-linéaire (#63 revue de code),
    reste sous sa cible : ce n'est plus une préparation "parfaite", et c'est
    documenté ainsi (voir `TestWeeklyVolumeTargetCurve` pour la formule)."""

    def setUp(self):
        self.activities = [
            run(0, 10000, 200), run(7, 12000, 300), run(14, 8000, 150),
            run(21, 18000, 1000, duration_s=9600), run(28, 10000, 200),
            run(35, 14000, 400), run(42, 9000, 150), run(49, 16000, 600),
        ]
        self.report = TS.trail_shape_report(objective(), self.activities, TODAY)

    def test_status_ok_with_a_moderate_to_high_score(self):
        self.assertEqual(self.report["status"], "ok")
        self.assertGreater(self.report["score"], 50)

    def test_longest_run_and_max_dplus_are_close_to_or_at_the_cap(self):
        by_id = {c["id"]: c for c in self.report["components"]}
        self.assertTrue(by_id["longest_run"]["eligible"])
        self.assertAlmostEqual(by_id["longest_run"]["actual"], 18000.0)
        self.assertGreater(by_id["longest_run"]["ratio"], 0.8)
        # D+ max observé (1000 m) dépasse largement la cible (600 m = 1200 * 0.5) :
        # le ratio ne doit JAMAIS dépasser 1.0, quel que soit le dépassement réel.
        self.assertEqual(by_id["max_dplus"]["ratio"], 1.0)

    def test_weekly_volume_is_eligible_but_under_its_now_higher_target(self):
        by_id = {c["id"]: c for c in self.report["components"]}
        self.assertTrue(by_id["weekly_volume"]["eligible"])
        self.assertLess(by_id["weekly_volume"]["ratio"], 1.0)
        self.assertEqual(by_id["weekly_volume"]["unit"], "km_effort")

    def test_max_dplus_unit_is_elevation_not_distance(self):
        by_id = {c["id"]: c for c in self.report["components"]}
        self.assertEqual(by_id["max_dplus"]["unit"], "m_elevation")
        self.assertNotEqual(by_id["max_dplus"]["unit"], by_id["longest_run"]["unit"])

    def test_durability_is_omitted_and_weights_are_renormalized(self):
        by_id = {c["id"]: c for c in self.report["components"]}
        self.assertFalse(by_id["durability"]["eligible"])
        self.assertIsNotNone(by_id["durability"]["reason"])
        eligible = [c for c in self.report["components"] if c["eligible"]]
        total = sum(c["weight_renormalized"] for c in eligible)
        self.assertAlmostEqual(total, 1.0, places=6)
        self.assertEqual(note_codes(self.report), {"durability_omitted"})

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

    def test_low_data_confidence_is_flagged_by_code(self):
        self.assertEqual(self.report["data_confidence"], "low")
        self.assertEqual(self.report["weeks_with_data"], 1)
        self.assertIn("low_confidence", note_codes(self.report))
        self.assertIn("semaine", note_message(self.report, "low_confidence"))

    def test_durability_omitted_no_long_run_at_all(self):
        by_id = {c["id"]: c for c in self.report["components"]}
        self.assertFalse(by_id["durability"]["eligible"])


class TestBothLowConfidenceAndFarHorizon(unittest.TestCase):
    """#63 revue de code (blocage 3) : deux notes actives à la fois — le code
    `low_confidence` doit rester repérable sans dépendre du mot « semaine »,
    présent aussi dans la note `far_horizon`."""

    def setUp(self):
        obj = objective(race_date="2028-06-15")
        activities = [run(2, 6000, 50, duration_s=2000)]
        self.report = TS.trail_shape_report(obj, activities, TODAY)

    def test_both_codes_are_present_and_distinguishable(self):
        codes = note_codes(self.report)
        self.assertIn("far_horizon", codes)
        self.assertIn("low_confidence", codes)
        far = note_message(self.report, "far_horizon")
        low = note_message(self.report, "low_confidence")
        self.assertIn("semaines", far)
        self.assertIn("semaine", low)
        self.assertNotEqual(far, low)


class TestDplusZeroVsMissing(unittest.TestCase):
    """#63 revue de code (should-fix 9) : D+ absent (`None`, profil incomplet)
    et D+ explicitement nul (route déclarée sans dénivelé) sont deux cas
    distincts, tous deux omis mais avec une raison différente — jamais
    confondus dans le message."""

    def test_missing_elevation_gain(self):
        obj = objective(elevation_gain_m=None)
        r = TS.trail_shape_report(obj, [run(0, 12000)], TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertFalse(by_id["max_dplus"]["eligible"])
        self.assertIn("non renseigné", by_id["max_dplus"]["reason"])

    def test_explicit_zero_elevation_gain(self):
        obj = objective(elevation_gain_m=0)
        r = TS.trail_shape_report(obj, [run(0, 12000)], TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertFalse(by_id["max_dplus"]["eligible"])
        self.assertIn("nul", by_id["max_dplus"]["reason"])
        self.assertIn("route", by_id["max_dplus"]["reason"])

    def test_both_are_omitted_the_same_way_for_the_score(self):
        r_none = TS.trail_shape_report(objective(elevation_gain_m=None), [run(0, 12000)], TODAY)
        r_zero = TS.trail_shape_report(objective(elevation_gain_m=0), [run(0, 12000)], TODAY)
        self.assertNotIn("max_dplus", {c["id"] for c in r_none["components"] if c["eligible"]})
        self.assertNotIn("max_dplus", {c["id"] for c in r_zero["components"] if c["eligible"]})


class TestFarHorizon(unittest.TestCase):
    def test_note_is_added_beyond_the_far_horizon_but_score_still_computes(self):
        obj = objective(race_date="2028-06-15")
        activities = [run(i * 7, 12000, 200) for i in range(8)]
        r = TS.trail_shape_report(obj, activities, TODAY)
        self.assertEqual(r["status"], "ok")
        self.assertIsNotNone(r["score"])
        self.assertIn("far_horizon", note_codes(r))


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
        self.assertEqual(by_id["durability"]["unit"], "pct_fade")
        # fade 5 % sur un plafond de 15 % (DURABILITY_MAX_ACCEPTABLE_FADE_PCT) -> ratio 2/3.
        self.assertAlmostEqual(by_id["durability"]["ratio"], 1 - 5.0 / TS.DURABILITY_MAX_ACCEPTABLE_FADE_PCT, places=3)

    def test_large_fade_floors_the_ratio_at_zero(self):
        act = run(10, 20000, 500, duration_s=9000)
        act["durability_gap_fade_pct"] = 90.0
        r = TS.trail_shape_report(objective(), [act], TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertEqual(by_id["durability"]["ratio"], 0.0)

    def test_negative_fade_negative_split_caps_the_ratio_at_one(self):
        # Une sortie plus rapide en seconde partie (négative splitting) donne
        # un fade négatif — le ratio ne doit JAMAIS dépasser 1.0.
        act = run(10, 20000, 500, duration_s=9000)
        act["durability_gap_fade_pct"] = -12.0
        r = TS.trail_shape_report(objective(), [act], TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertEqual(by_id["durability"]["ratio"], 1.0)


class TestHikingAndWalkingExclusion(unittest.TestCase):
    """#63 revue de code (should-fix 7) : la randonnée/marche compte pour le
    D+ max d'une séance (préparation légitime au dénivelé) mais PAS pour le
    volume hebdomadaire ni la plus longue sortie (pas un stimulus d'allure
    comparable à la course à pied)."""

    def test_hiking_does_not_count_toward_weekly_volume_or_longest_run(self):
        obj = objective()
        activities = [run(i * 7, 25000, 1500, sport="hiking") for i in range(6)]
        r = TS.trail_shape_report(obj, activities, TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertEqual(by_id["weekly_volume"]["actual"], 0.0)
        self.assertEqual(by_id["longest_run"]["actual"], 0.0)

    def test_hiking_counts_toward_max_dplus(self):
        obj = objective()
        activities = [run(0, 25000, 1500, sport="hiking")]
        r = TS.trail_shape_report(obj, activities, TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertTrue(by_id["max_dplus"]["eligible"])
        self.assertEqual(by_id["max_dplus"]["actual"], 1500.0)

    def test_walking_is_excluded_the_same_way_as_hiking(self):
        obj = objective()
        activities = [run(0, 8000, 100, sport="walking")]
        r = TS.trail_shape_report(obj, activities, TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertEqual(by_id["weekly_volume"]["actual"], 0.0)
        self.assertEqual(by_id["longest_run"]["actual"], 0.0)
        self.assertTrue(by_id["max_dplus"]["eligible"])


class TestRoadObjectiveWithoutElevation(unittest.TestCase):
    """Objectif route sans D+ renseigné (`elevation_gain_m` absent) : la
    composante D+ max est omise structurellement, jamais notée à 0."""

    def test_max_dplus_component_is_omitted(self):
        obj = objective(elevation_gain_m=None)
        activities = [run(i * 7, 12000, 0) for i in range(6)]
        r = TS.trail_shape_report(obj, activities, TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        self.assertFalse(by_id["max_dplus"]["eligible"])
        self.assertIn("renseigné", by_id["max_dplus"]["reason"])
        eligible_ids = {c["id"] for c in r["components"] if c["eligible"]}
        self.assertNotIn("max_dplus", eligible_ids)


class TestRaceDayActivityExcluded(unittest.TestCase):
    """#63 revue de code (should-fix 9) : décision explicite — une activité
    déjà loggée le jour même de la course (`date == objective.race_date`) est
    exclue de toute composante, jamais comptée comme une séance de
    préparation (voir la docstring du module)."""

    def test_activity_dated_on_race_day_is_excluded_everywhere(self):
        obj = objective(race_date=TODAY.isoformat())
        race_activity = {"date": TODAY.isoformat(), "sport": "trail", "distance_m": 21100.0,
                          "elevation_gain_m": 1200.0, "duration_s": 9000, "durability_gap_fade_pct": 8.0}
        training = run(3, 10000, 200)
        r = TS.trail_shape_report(obj, [race_activity, training], TODAY)
        by_id = {c["id"]: c for c in r["components"]}
        # Sans l'exclusion, la plus longue sortie serait 21100 m (la course
        # elle-même) et le D+ max 1200 m : elle doit rester la séance d'entraînement.
        self.assertEqual(by_id["longest_run"]["actual"], 10000.0)
        self.assertEqual(by_id["max_dplus"]["actual"], 200.0)
        self.assertFalse(by_id["durability"]["eligible"])


class TestWeightsSumToOne(unittest.TestCase):
    def test_component_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(TS.COMPONENT_WEIGHTS.values()), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
