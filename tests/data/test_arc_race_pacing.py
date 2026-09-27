"""Palier D — allures de course par segment depuis le modèle personnel (#59,
épopée #23).

Familles de tests :
- `segment_course` : GPX de fixture (coordonnées fictives, zone
  `SAFE_LAT_RANGE`/`SAFE_LON_RANGE` du lint #49) à profil connu (montée,
  plat, descente) -> pentes moyennes attendues, bornes kilométriques
  croissantes, identifiants stables (`s01`, `s02`…), déterminisme (deux
  appels identiques rendent EXACTEMENT le même résultat).
- `predict_segments`/`fade_speed_multiplier`/`heat_time_factor` : arithmétique
  main-calculée sur des paniers de modèle connus (personnel avec dispersion,
  générique sans dispersion) — temps de segment attendus, scénarios
  safe/realistic/ambitious, provenance par segment, repli générique quand
  aucun panier ne couvre la pente.
- `compute_passages`/`check_cutoffs` : temps cumulés, arrêts ravito, marge de
  barrière horaire (ok/tendu/hors délai).
- `build_race_plan` : assemblage bout en bout, cas générique (aucune
  dispersion personnelle) avec provenance explicitement "generic".
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import arc_race_pacing as RP  # noqa: E402

# Zone fictive conventionnelle du dépôt pour toute coordonnée de test (#49,
# tests/lint/test_synthetic_no_real_data.py) : Pacifique Sud, loin de toute côte.
SAFE_LAT = -40.0
SAFE_LON = -140.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(SAFE_LAT))


def _straight_course(profile, step_m=5.0):
    """Construit une trace GPX synthétique rectiligne (latitude fixe, longitude
    croissante) — `profile(d)` rend l'altitude à la distance cumulée `d`
    (mètres). Utilise le mètre comme unité de distance ; pas de bruit GPS
    (déterminisme total, seul l'effet du lissage d'altitude aux bords
    d'inflexion de pente doit être toléré dans les assertions)."""
    deg_step = step_m / M_PER_DEG_LON
    total_m = profile.total_m
    n = int(total_m / step_m) + 1
    pts = []
    for i in range(n):
        d = min(i * step_m, total_m)
        pts.append({"lat": SAFE_LAT, "lon": SAFE_LON + i * deg_step, "ele": profile(d)})
    return pts


class _ClimbFlatDescentProfile:
    """0-1000 m : montée à 8 % ; 1000-2000 m : plat ; 2000-3000 m : descente à 8 %."""
    total_m = 3000.0

    def __call__(self, d):
        if d <= 1000.0:
            return d * 0.08
        if d <= 2000.0:
            return 80.0
        return 80.0 - (d - 2000.0) * 0.08


class TestSegmentCourse(unittest.TestCase):
    def setUp(self):
        self.pts = _straight_course(_ClimbFlatDescentProfile())

    def test_segments_cover_the_whole_course_without_gap_or_overlap(self):
        segs = RP.segment_course(self.pts, target_segment_m=500.0)
        self.assertGreater(len(segs), 0)
        self.assertEqual(segs[0]["km_start"], 0.0)
        self.assertAlmostEqual(segs[-1]["km_end"], 3000.0 / 1000.0, delta=0.01)
        for a, b in zip(segs, segs[1:]):
            self.assertEqual(a["km_end"], b["km_start"])

    def test_segment_ids_are_stable_and_zero_padded(self):
        segs = RP.segment_course(self.pts, target_segment_m=500.0)
        ids = [s["id"] for s in segs]
        self.assertEqual(ids, sorted(ids))
        self.assertTrue(all(i.startswith("s") for i in ids))
        self.assertEqual(len(set(ids)), len(ids))

    def test_climb_segments_have_positive_grade_and_descent_negative(self):
        segs = RP.segment_course(self.pts, target_segment_m=400.0)
        first = segs[0]
        last = segs[-1]
        self.assertGreater(first["grade_mean_pct"], 5.0, first)
        self.assertLess(last["grade_mean_pct"], -5.0, last)
        self.assertGreater(first["elevation_gain_m"], 0)
        self.assertGreater(last["elevation_loss_m"], 0)

    def test_deterministic_across_calls(self):
        a = RP.segment_course(self.pts, target_segment_m=500.0)
        b = RP.segment_course(self.pts, target_segment_m=500.0)
        self.assertEqual(a, b)

    def test_flat_grade_is_near_zero(self):
        segs = RP.segment_course(self.pts, target_segment_m=250.0)
        # Segment(s) dont le MILIEU tombe dans la portion plate (1000-2000 m), loin
        # des bords d'inflexion où le lissage/la fenêtre de pente mélange encore la
        # côte/descente avec le plat.
        flat = [s for s in segs if 1.1 <= (s["km_start"] + s["km_end"]) / 2 <= 1.9]
        self.assertTrue(flat, segs)
        for s in flat:
            self.assertLess(abs(s["grade_mean_pct"]), 1.0, s)

    def test_similar_grade_segments_get_merged_on_flat_section(self):
        # Sur 1000 m de plat avec une longueur cible de 100 m, la fusion doit
        # réduire fortement le nombre de segments (jamais 10 segments de 100 m
        # tous à ~0 % — voir ASSUMPTIONS["segmentation"]).
        pts = _straight_course(_ClimbFlatDescentProfile(), step_m=5.0)
        segs = RP.segment_course(pts, target_segment_m=100.0)
        flat_segs = [s for s in segs if 1.0 <= s["km_start"] < 2.0]
        self.assertLess(len(flat_segs), 7, flat_segs)

    def test_too_few_points_returns_empty(self):
        self.assertEqual(RP.segment_course([{"lat": SAFE_LAT, "lon": SAFE_LON, "ele": 0}]), [])


PERSONAL_BINS = [
    {"grade_mid": -0.10, "speed_ms": 3.5, "source": "personal", "ci_low_speed_ms": 3.3, "ci_high_speed_ms": 3.7,
     "hr_bpm": 140},
    {"grade_mid": 0.0, "speed_ms": 3.0, "source": "personal", "ci_low_speed_ms": 2.8, "ci_high_speed_ms": 3.2,
     "hr_bpm": 145},
    {"grade_mid": 0.10, "speed_ms": 2.0, "source": "personal", "ci_low_speed_ms": 1.8, "ci_high_speed_ms": 2.2,
     "hr_bpm": 155},
]

GENERIC_BINS = [
    {"grade_mid": 0.0, "speed_ms": 3.0, "source": "generic", "ci_low_speed_ms": None, "ci_high_speed_ms": None,
     "hr_bpm": None},
]


class TestPredictSegments(unittest.TestCase):
    def test_flat_personal_segment_predicted_time_hand_computed(self):
        # Panier exact au point milieu 0.0 (pas d'interpolation) : vitesse
        # cible = 3.0 m/s -> 500 m / 3.0 = 166.67 s (arrondi à 166.7 dans le module).
        segs = [{"id": "s01", "km_start": 0.0, "km_end": 0.5, "distance_m": 500.0,
                 "grade_mean_pct": 0.0, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0}]
        out = RP.predict_segments(segs, PERSONAL_BINS, fade_pct=0.0, heat_factor=1.0)
        self.assertEqual(out[0]["source"], "personal")
        self.assertAlmostEqual(out[0]["predicted_time_s"]["realistic"], 500.0 / 3.0, places=1)
        self.assertAlmostEqual(out[0]["predicted_time_s"]["safe"], 500.0 / 2.8, places=1)
        self.assertAlmostEqual(out[0]["predicted_time_s"]["ambitious"], 500.0 / 3.2, delta=0.1)
        # safe (le plus lent) doit toujours être le temps le plus long.
        self.assertGreater(out[0]["predicted_time_s"]["safe"], out[0]["predicted_time_s"]["realistic"])
        self.assertGreater(out[0]["predicted_time_s"]["realistic"], out[0]["predicted_time_s"]["ambitious"])

    def test_climb_segment_interpolates_between_bins(self):
        # Pente à 5 %, entre les paniers 0.0 (3.0 m/s) et 0.10 (2.0 m/s) :
        # frac = 0.5 -> vitesse cible = 2.5 m/s -> 1000 / 2.5 = 400 s.
        segs = [{"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
                 "grade_mean_pct": 5.0, "elevation_gain_m": 50.0, "elevation_loss_m": 0.0}]
        out = RP.predict_segments(segs, PERSONAL_BINS, fade_pct=0.0, heat_factor=1.0)
        self.assertAlmostEqual(out[0]["predicted_time_s"]["realistic"], 1000.0 / 2.5, places=1)

    def test_generic_segment_uses_fixed_percentage_scenarios(self):
        segs = [{"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
                 "grade_mean_pct": 0.0, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0}]
        out = RP.predict_segments(segs, GENERIC_BINS, fade_pct=0.0, heat_factor=1.0)
        self.assertEqual(out[0]["source"], "generic")
        realistic = out[0]["predicted_time_s"]["realistic"]
        safe = out[0]["predicted_time_s"]["safe"]
        ambitious = out[0]["predicted_time_s"]["ambitious"]
        self.assertAlmostEqual(realistic, 1000.0 / 3.0, places=1)
        self.assertGreater(safe, realistic)
        self.assertGreater(realistic, ambitious)

    def test_no_model_bins_predicts_no_time_and_flags_reason(self):
        segs = [{"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
                 "grade_mean_pct": 0.0, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0}]
        out = RP.predict_segments(segs, [], fade_pct=0.0, heat_factor=1.0)
        self.assertIsNone(out[0]["predicted_time_s"]["realistic"])
        self.assertEqual(out[0]["reason_code"], "no_model")
        self.assertTrue(out[0]["notes"])

    def test_heat_factor_slows_every_scenario_uniformly(self):
        segs = [{"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
                 "grade_mean_pct": 0.0, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0}]
        base = RP.predict_segments(segs, PERSONAL_BINS, fade_pct=0.0, heat_factor=1.0)
        hot = RP.predict_segments(segs, PERSONAL_BINS, fade_pct=0.0, heat_factor=1.10)
        for scenario in RP.SCENARIOS:
            self.assertAlmostEqual(
                hot[0]["predicted_time_s"][scenario], base[0]["predicted_time_s"][scenario] * 1.10, delta=0.1)

    def test_provenance_summary_shares_sum_to_100(self):
        segs = [{"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
                 "grade_mean_pct": 0.0, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0}]
        personal_out = RP.predict_segments(segs, PERSONAL_BINS, fade_pct=0.0, heat_factor=1.0)
        generic_out = RP.predict_segments(segs, GENERIC_BINS, fade_pct=0.0, heat_factor=1.0)
        mixed = personal_out + generic_out
        summary = RP.provenance_summary(mixed)
        self.assertAlmostEqual(summary["personal_pct"], 50.0)
        self.assertAlmostEqual(summary["generic_pct"], 50.0)
        self.assertAlmostEqual(summary["mixed_pct"], 0.0)


class TestFade(unittest.TestCase):
    def test_no_fade_in_first_third(self):
        self.assertEqual(RP.fade_speed_multiplier(0.0, 10.0), 1.0)
        self.assertEqual(RP.fade_speed_multiplier(1.0 / 3.0, 10.0), 1.0)

    def test_full_fade_at_finish(self):
        self.assertAlmostEqual(RP.fade_speed_multiplier(1.0, 9.0), 0.91)

    def test_fade_ramps_linearly_between_first_third_and_finish(self):
        # À mi-chemin entre le premier tiers (1/3) et l'arrivée (1.0), soit
        # km_frac = 2/3 : la moitié du fade est appliquée.
        self.assertAlmostEqual(RP.fade_speed_multiplier(2.0 / 3.0, 10.0), 0.95, places=4)

    def test_zero_fade_pct_is_a_no_op(self):
        self.assertEqual(RP.fade_speed_multiplier(1.0, 0.0), 1.0)


class TestHeat(unittest.TestCase):
    def test_no_forecast_means_no_adjustment(self):
        factor, notes = RP.heat_time_factor(None)
        self.assertEqual(factor, 1.0)
        self.assertTrue(notes)

    def test_moderate_temperature_is_a_no_op(self):
        factor, notes = RP.heat_time_factor(18.0)
        self.assertEqual(factor, 1.0)
        self.assertEqual(notes, [])

    def test_hot_forecast_applies_documented_time_factor(self):
        factor, notes = RP.heat_time_factor(30.0)
        self.assertAlmostEqual(factor, RP.HEAT_HOT_TIME_FACTOR)
        self.assertTrue(notes)

    def test_hot_and_unacclimated_stacks_the_extra_factor(self):
        factor, _ = RP.heat_time_factor(30.0, acclimated=False)
        self.assertAlmostEqual(factor, RP.HEAT_HOT_TIME_FACTOR * RP.HEAT_UNACCLIMATED_EXTRA_FACTOR)

    def test_hot_and_acclimated_does_not_stack(self):
        factor, _ = RP.heat_time_factor(30.0, acclimated=True)
        self.assertAlmostEqual(factor, RP.HEAT_HOT_TIME_FACTOR)

    def test_cold_forecast_applies_documented_time_factor(self):
        factor, notes = RP.heat_time_factor(2.0)
        self.assertAlmostEqual(factor, RP.HEAT_COLD_TIME_FACTOR)
        self.assertTrue(notes)


class TestPassagesAndCutoffs(unittest.TestCase):
    def _segments(self):
        segs = [
            {"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
             "grade_mean_pct": 0.0, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0},
            {"id": "s02", "km_start": 1.0, "km_end": 2.0, "distance_m": 1000.0,
             "grade_mean_pct": 0.0, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0},
        ]
        return RP.predict_segments(segs, GENERIC_BINS, fade_pct=0.0, heat_factor=1.0)

    def test_aid_station_stop_time_is_added_to_every_later_segment(self):
        segs = self._segments()
        stations = [{"km": 1.0, "name": "Ravito", "stop_s": 60.0}]
        passages = RP.compute_passages(segs, stations)
        before = segs[0]["predicted_time_s"]["realistic"]
        after_two_segments = segs[0]["predicted_time_s"]["realistic"] + segs[1]["predicted_time_s"]["realistic"]
        self.assertAlmostEqual(passages["segment_passages"][0]["realistic"], round(before))
        # Le second passage inclut les 60 s d'arrêt ravito en plus des deux segments.
        self.assertAlmostEqual(passages["totals_s"]["realistic"], round(after_two_segments + 60.0), delta=1)

    def test_default_aid_station_stop_when_unspecified(self):
        segs = self._segments()
        stations = [{"km": 1.0, "name": "Ravito"}]
        passages = RP.compute_passages(segs, stations)
        total_running = sum(s["predicted_time_s"]["realistic"] for s in segs)
        self.assertAlmostEqual(
            passages["totals_s"]["realistic"], round(total_running + RP.DEFAULT_AID_STATION_STOP_S), delta=1)

    def test_cutoff_with_large_margin_is_ok(self):
        segs = self._segments()
        stations = [{"km": 1.0, "name": "Ravito", "cutoff": "23:59"}]
        from datetime import datetime
        passages = RP.compute_passages(segs, stations)
        cutoffs = RP.check_cutoffs(passages["aid_station_passages"], stations, datetime(2026, 11, 15, 7, 0))
        self.assertEqual(cutoffs[0]["realistic"]["status"], "ok")
        self.assertGreater(cutoffs[0]["realistic"]["margin_s"], RP.CUTOFF_MARGIN_OK_S)

    def test_cutoff_missed_is_flagged(self):
        segs = self._segments()
        stations = [{"km": 1.0, "name": "Ravito", "cutoff": "07:00"}]
        from datetime import datetime
        passages = RP.compute_passages(segs, stations)
        cutoffs = RP.check_cutoffs(passages["aid_station_passages"], stations, datetime(2026, 11, 15, 7, 0))
        self.assertEqual(cutoffs[0]["realistic"]["status"], "hors_delai")
        self.assertLess(cutoffs[0]["realistic"]["margin_s"], 0)

    def test_station_without_cutoff_is_absent_from_result(self):
        segs = self._segments()
        stations = [{"km": 1.0, "name": "Ravito"}]
        from datetime import datetime
        passages = RP.compute_passages(segs, stations)
        cutoffs = RP.check_cutoffs(passages["aid_station_passages"], stations, datetime(2026, 11, 15, 7, 0))
        self.assertEqual(cutoffs, [])


class TestBuildRacePlan(unittest.TestCase):
    def test_generic_end_to_end_plan_is_internally_consistent(self):
        pts = _straight_course(_ClimbFlatDescentProfile())
        plan = RP.build_race_plan(
            pts, GENERIC_BINS, aid_stations=[{"km": 1.5, "name": "Ravito 1", "cutoff": "23:00"}],
            fade_pct=0.0, fade_source="generic", temp_max_c=None, acclimated=None,
            start_time="07:00", race_date="2026-11-15", segment_m=500.0)
        self.assertGreater(len(plan["segments"]), 0)
        self.assertEqual(plan["provenance_summary"]["personal_pct"], 0.0)
        self.assertEqual(plan["provenance_summary"]["generic_pct"], 100.0)
        for scenario in RP.SCENARIOS:
            self.assertIn(scenario, plan["totals"]["time_s"])
        self.assertEqual(len(plan["cutoffs"]), 1)
        self.assertEqual(plan["cutoffs"][0]["realistic"]["status"], "ok")
        # safe (le plus lent) prend toujours plus de temps que ambitious.
        self.assertGreater(plan["totals"]["time_s"]["safe"], plan["totals"]["time_s"]["ambitious"])

    def test_fade_makes_the_plan_slower_than_without_fade(self):
        pts = _straight_course(_ClimbFlatDescentProfile())
        no_fade = RP.build_race_plan(pts, GENERIC_BINS, fade_pct=0.0, fade_source="generic",
                                      start_time="07:00", race_date="2026-11-15", segment_m=500.0)
        with_fade = RP.build_race_plan(pts, GENERIC_BINS, fade_pct=8.0, fade_source="generic",
                                        start_time="07:00", race_date="2026-11-15", segment_m=500.0)
        self.assertGreater(with_fade["totals"]["time_s"]["realistic"], no_fade["totals"]["time_s"]["realistic"])


if __name__ == "__main__":
    unittest.main()
