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
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import arc_index as IDX  # noqa: E402
import arc_metrics as M  # noqa: E402
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


class _LongClimbFlatDescentProfile:
    """Même forme que `_ClimbFlatDescentProfile`, mise à l'échelle pour que la
    course prédite dépasse largement le seuil de sortie longue (90 min,
    `arc_metrics.LONG_RUN_MIN_DURATION_S`) : le fade ne doit alors PAS être
    réduit par l'échelonnement durée/#48 (`ASSUMPTIONS["fade"]`), et son effet
    doit rester visible après arrondi à la minute des totaux cumulés."""
    total_m = 24000.0

    def __call__(self, d):
        if d <= 8000.0:
            return d * 0.03
        if d <= 16000.0:
            return 240.0
        return 240.0 - (d - 16000.0) * 0.03


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
        # cible = 3.0 m/s -> 500 m / 3.0 = 166.67 s, arrondi à la seconde (167).
        # `safe`/`ambitious` passent par le plancher générique (ASSUMPTIONS
        # ["scenarios"]) : la dispersion mesurée (ci_low=2.8, ci_high=3.2) est
        # plus ÉTROITE côté « safe » que le plancher générique (speed × 0.92 =
        # 2.76 < 2.8) -> safe = 500 / 2.76 = 181 s ; côté « ambitious », la
        # mesure (3.2) est déjà PLUS large que le plancher (speed × 1.06 =
        # 3.18) -> ambitious = 500 / 3.2 = 156 s (mesure conservée).
        segs = [{"id": "s01", "km_start": 0.0, "km_end": 0.5, "distance_m": 500.0,
                 "grade_mean_pct": 0.0, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0}]
        out = RP.predict_segments(segs, PERSONAL_BINS, fade_pct=0.0, heat_factor=1.0)
        self.assertEqual(out[0]["source"], "personal")
        self.assertEqual(out[0]["predicted_time_s"]["realistic"], round(500.0 / 3.0))
        self.assertEqual(out[0]["predicted_time_s"]["safe"], round(500.0 / 2.76))
        self.assertEqual(out[0]["predicted_time_s"]["ambitious"], round(500.0 / 3.2))
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
        self.assertEqual(realistic, round(1000.0 / 3.0))
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
        # Chaque scénario est arrondi INDÉPENDAMMENT à la seconde (`base` et `hot`) :
        # une marge d'une seconde absorbe le double arrondi.
        for scenario in RP.SCENARIOS:
            self.assertAlmostEqual(
                hot[0]["predicted_time_s"][scenario], base[0]["predicted_time_s"][scenario] * 1.10, delta=1.0)

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
        # Calibré pour que la MOYENNE du dernier tiers égale fade_pct (voir
        # ASSUMPTIONS["fade"]) : à l'arrivée (t=1), réduction = 1 × (4/3) ×
        # (9/100) = 12 % -> multiplicateur 0.88 (PAS 0.91, qui ne ferait que
        # 0,75 × 9 % de moyenne sur le dernier tiers).
        self.assertAlmostEqual(RP.fade_speed_multiplier(1.0, 9.0), 0.88)

    def test_fade_ramps_linearly_between_first_third_and_finish(self):
        # À mi-chemin entre le premier tiers (1/3) et l'arrivée (1.0), soit
        # km_frac = 2/3 : t = 0.5, réduction = 0.5 × (4/3) × (10/100) ≈ 6,67 %.
        self.assertAlmostEqual(RP.fade_speed_multiplier(2.0 / 3.0, 10.0), 1.0 - 0.5 * (4.0 / 3.0) * 0.10, places=6)

    def test_last_third_mean_reduction_equals_fade_pct(self):
        # Preuve directe de la calibration (ASSUMPTIONS["fade"]) : la MOYENNE
        # de la réduction sur le dernier tiers (échantillonné finement) égale
        # `fade_pct`, pas seulement la valeur ponctuelle à l'arrivée.
        fade_pct = 12.0
        n = 1000
        reductions = [1.0 - RP.fade_speed_multiplier(2.0 / 3.0 + i / n * (1.0 / 3.0), fade_pct) for i in range(n)]
        self.assertAlmostEqual(sum(reductions) / n, fade_pct / 100.0, places=3)

    def test_zero_fade_pct_is_a_no_op(self):
        self.assertEqual(RP.fade_speed_multiplier(1.0, 0.0), 1.0)

    def test_extreme_fade_never_goes_below_the_floor(self):
        self.assertGreaterEqual(RP.fade_speed_multiplier(1.0, 500.0), RP.FADE_MIN_SPEED_FACTOR)


class TestScaleFadeToDuration(unittest.TestCase):
    def test_race_shorter_than_long_run_threshold_scales_fade_down(self):
        half_threshold_s = RP.M.LONG_RUN_MIN_DURATION_S / 2.0
        self.assertAlmostEqual(RP.scale_fade_to_duration(10.0, half_threshold_s), 5.0)

    def test_race_at_or_above_threshold_keeps_fade_unscaled(self):
        self.assertEqual(RP.scale_fade_to_duration(10.0, RP.M.LONG_RUN_MIN_DURATION_S), 10.0)
        self.assertEqual(RP.scale_fade_to_duration(10.0, RP.M.LONG_RUN_MIN_DURATION_S * 2), 10.0)

    def test_unknown_duration_leaves_fade_unchanged(self):
        self.assertEqual(RP.scale_fade_to_duration(10.0, None), 10.0)

    def test_zero_fade_is_a_no_op(self):
        self.assertEqual(RP.scale_fade_to_duration(0.0, 60.0), 0.0)


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
        # Les temps de passage/totaux cumulés sont arrondis à la MINUTE
        # (`RP.PASSAGE_ROUND_S`), jamais à la seconde — voir
        # `ASSUMPTIONS["cutoffs"]`/le docstring du module sur la précision.
        segs = self._segments()
        stations = [{"km": 1.0, "name": "Ravito", "stop_s": 60.0}]
        passages = RP.compute_passages(segs, stations)
        before = segs[0]["predicted_time_s"]["realistic"]
        after_two_segments = segs[0]["predicted_time_s"]["realistic"] + segs[1]["predicted_time_s"]["realistic"]
        self.assertEqual(passages["segment_passages"][0]["realistic"], RP._round_passage(before))
        # Le second passage inclut les 60 s d'arrêt ravito en plus des deux segments.
        self.assertEqual(passages["totals_s"]["realistic"], RP._round_passage(after_two_segments + 60.0))

    def test_default_aid_station_stop_when_unspecified(self):
        segs = self._segments()
        stations = [{"km": 1.0, "name": "Ravito"}]
        passages = RP.compute_passages(segs, stations)
        total_running = sum(s["predicted_time_s"]["realistic"] for s in segs)
        self.assertEqual(
            passages["totals_s"]["realistic"], RP._round_passage(total_running + RP.DEFAULT_AID_STATION_STOP_S))

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
        # Course longue (~2h13 à 3 m/s, largement au-dessus du seuil de sortie
        # longue de 90 min) : le fade n'est donc PAS réduit par l'échelonnement
        # durée/#48, et son effet reste visible après arrondi à la minute.
        pts = _straight_course(_LongClimbFlatDescentProfile(), step_m=20.0)
        no_fade = RP.build_race_plan(pts, GENERIC_BINS, fade_pct=0.0, fade_source="generic",
                                      start_time="07:00", race_date="2026-11-15", segment_m=750.0)
        with_fade = RP.build_race_plan(pts, GENERIC_BINS, fade_pct=8.0, fade_source="generic",
                                        start_time="07:00", race_date="2026-11-15", segment_m=750.0)
        self.assertEqual(with_fade["fade_pct_applied"], 8.0)
        self.assertGreater(with_fade["totals"]["time_s"]["realistic"], no_fade["totals"]["time_s"]["realistic"])

    def test_fade_is_scaled_down_for_a_race_shorter_than_the_long_run_threshold(self):
        # Course courte (~17 min à 3 m/s) : un fade mesuré sur sortie longue
        # (90 min) ne doit s'appliquer que PARTIELLEMENT (ASSUMPTIONS["fade"]).
        pts = _straight_course(_ClimbFlatDescentProfile())
        plan = RP.build_race_plan(pts, GENERIC_BINS, fade_pct=8.0, fade_source="generic",
                                   start_time="07:00", race_date="2026-11-15", segment_m=500.0)
        self.assertLess(plan["fade_pct_applied"], 8.0)
        self.assertGreater(plan["fade_pct_applied"], 0.0)
        self.assertTrue(plan["fade_notes"])

    def test_fade_is_time_neutral_when_an_intensity_prediction_exists(self):
        # #59, 2ᵉ revue de code, should-fix : Riegel/VDOT intègrent déjà une
        # dégradation d'endurance sur la distance — le fade ne doit alors PAS
        # ajouter de temps NET, seulement redistribuer (plus rapide en début,
        # plus lent en fin).
        pts = _straight_course(_LongClimbFlatDescentProfile(), step_m=20.0)
        no_fade = RP.build_race_plan(pts, GENERIC_BINS, fade_pct=0.0, fade_source="generic",
                                      intensity_factor=1.3, intensity_source="riegel",
                                      start_time="07:00", race_date="2026-11-15", segment_m=750.0)
        with_fade = RP.build_race_plan(pts, GENERIC_BINS, fade_pct=8.0, fade_source="generic",
                                        intensity_factor=1.3, intensity_source="riegel",
                                        start_time="07:00", race_date="2026-11-15", segment_m=750.0)
        # Même total (à l'arrondi minute près) malgré un fade non nul...
        self.assertEqual(with_fade["totals"]["time_s"]["realistic"], no_fade["totals"]["time_s"]["realistic"])
        # ... mais une répartition différente : le premier segment est plus
        # RAPIDE avec fade (le temps économisé en début compense le
        # ralentissement de fin), preuve que le fade a bien un effet local.
        first_no_fade = no_fade["segments"][0]["predicted_time_s"]["realistic"]
        first_with_fade = with_fade["segments"][0]["predicted_time_s"]["realistic"]
        self.assertLess(first_with_fade, first_no_fade)
        self.assertTrue(any("neutre" in n.lower() for n in with_fade["fade_notes"]))

    def test_fade_still_nets_extra_time_without_an_intensity_prediction(self):
        # Sans Riegel/VDOT (intensity_source == "none"), le fade reste un vrai
        # ralentissement NET, comme avant #59 (2ᵉ revue) : rien à double-compter.
        pts = _straight_course(_LongClimbFlatDescentProfile(), step_m=20.0)
        no_fade = RP.build_race_plan(pts, GENERIC_BINS, fade_pct=0.0, fade_source="generic",
                                      start_time="07:00", race_date="2026-11-15", segment_m=750.0)
        with_fade = RP.build_race_plan(pts, GENERIC_BINS, fade_pct=8.0, fade_source="generic",
                                        start_time="07:00", race_date="2026-11-15", segment_m=750.0)
        self.assertGreater(with_fade["totals"]["time_s"]["realistic"], no_fade["totals"]["time_s"]["realistic"])


# ---------------------------------------------------------------------------
# Terrain vallonné : intégration point par point (revue de code #59, blocant)
# ---------------------------------------------------------------------------

class _RollingProfile:
    """Aller-retour +12 %/-12 % tous les 375 m sur 750 m : pente MOYENNE quasi
    nulle, mais un temps réel bien plus long qu'un vrai plat de même longueur
    (voir `ASSUMPTIONS["rolling_terrain"]`)."""
    total_m = 750.0

    def __call__(self, d):
        if d <= 375.0:
            return d * 0.12
        return 375.0 * 0.12 - (d - 375.0) * 0.12


class TestRollingTerrainIntegration(unittest.TestCase):
    def test_rolling_terrain_is_slower_than_naive_average_grade_time(self):
        pts = _straight_course(_RollingProfile(), step_m=5.0)
        segs = RP.segment_course(pts, target_segment_m=750.0, merge_grade_delta_pct=999.0)
        # Un seul segment couvre tout l'aller-retour (fusion forcée pour ce test :
        # ce qui nous intéresse est l'intégration DANS un segment, pas la
        # segmentation elle-même).
        self.assertEqual(len(segs), 1)
        self.assertAlmostEqual(segs[0]["grade_mean_pct"], 0.0, delta=0.5)

        bins = [
            {"grade_mid": -0.12, "speed_ms": 4.0, "source": "personal",
             "ci_low_speed_ms": 3.8, "ci_high_speed_ms": 4.2, "hr_bpm": 130},
            {"grade_mid": 0.0, "speed_ms": 3.0, "source": "personal",
             "ci_low_speed_ms": 2.8, "ci_high_speed_ms": 3.2, "hr_bpm": 145},
            {"grade_mid": 0.12, "speed_ms": 1.5, "source": "personal",
             "ci_low_speed_ms": 1.3, "ci_high_speed_ms": 1.7, "hr_bpm": 165},
        ]
        integrated = RP.predict_segments(segs, bins, fade_pct=0.0, heat_factor=1.0)
        integrated_time = integrated[0]["predicted_time_s"]["realistic"]

        # Repère de comparaison : le temps qu'on obtiendrait en prédisant UNE
        # SEULE FOIS sur la pente moyenne (l'ancien comportement, bogué) — un
        # segment "à la main" sans `_profile` retombe sur ce calcul (voir
        # `_segment_intervals`).
        naive_seg = [{"id": "naive", "km_start": segs[0]["km_start"], "km_end": segs[0]["km_end"],
                      "distance_m": segs[0]["distance_m"], "grade_mean_pct": segs[0]["grade_mean_pct"],
                      "elevation_gain_m": segs[0]["elevation_gain_m"],
                      "elevation_loss_m": segs[0]["elevation_loss_m"]}]
        naive = RP.predict_segments(naive_seg, bins, fade_pct=0.0, heat_factor=1.0)
        naive_time = naive[0]["predicted_time_s"]["realistic"]

        # Le vrai temps intégré doit être NETTEMENT plus lent que le calcul naïf
        # sur la pente moyenne (~0 %, vitesse 3.0 m/s) — la montée coûte plus
        # que ce que la descente ne fait gagner (modèle de Minetti).
        self.assertGreater(integrated_time, naive_time)
        self.assertGreater(integrated_time, segs[0]["distance_m"] / 3.0 * 1.05)


# ---------------------------------------------------------------------------
# Panier central snapé sur 0 % (revue de code #59, should-fix)
# ---------------------------------------------------------------------------

class TestSnapGradeToBin(unittest.TestCase):
    def test_tiny_grade_inside_the_center_bin_is_snapped_to_zero_without_lo_hi_info(self):
        # Aucun panier ne porte `grade_lo`/`grade_hi` (fixtures de test à un
        # seul point) : repli sur le panier CENTRAL canonique du modèle.
        tiny = RP._CENTER_BIN_HI / 2.0
        self.assertEqual(RP._snap_grade_to_bin(tiny, []), 0.0)
        self.assertEqual(RP._snap_grade_to_bin(-tiny, []), 0.0)

    def test_grade_outside_the_center_bin_is_left_unchanged_without_lo_hi_info(self):
        outside = RP._CENTER_BIN_HI + 0.05
        self.assertEqual(RP._snap_grade_to_bin(outside, []), outside)

    def test_none_grade_is_left_unchanged(self):
        self.assertIsNone(RP._snap_grade_to_bin(None, []))

    def test_gps_noise_near_flat_does_not_spuriously_produce_mixed_source(self):
        # Panier plat personnel voisin d'un panier générique (SANS grade_lo/hi,
        # cas test) : sans le snap, une pente de bruit GPS de quelques dixièmes
        # de point interpolerait entre les deux et étiquetterait à tort le
        # segment "mixed".
        bins = [
            {"grade_mid": 0.0, "speed_ms": 3.0, "source": "personal",
             "ci_low_speed_ms": 2.8, "ci_high_speed_ms": 3.2, "hr_bpm": 145},
            {"grade_mid": 0.10, "speed_ms": 2.0, "source": "generic",
             "ci_low_speed_ms": None, "ci_high_speed_ms": None, "hr_bpm": None},
        ]
        noisy_grade_pct = (RP._CENTER_BIN_HI / 2.0) * 100.0
        seg = [{"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
                "grade_mean_pct": noisy_grade_pct, "elevation_gain_m": 3.0, "elevation_loss_m": 0.0}]
        out = RP.predict_segments(seg, bins, fade_pct=0.0, heat_factor=1.0)
        self.assertEqual(out[0]["source"], "personal")

    def test_grade_inside_a_real_personal_bin_range_snaps_to_that_bin_even_off_center(self):
        # Reproduit le rapport de revue #59 (58 % de "mixed" sur un profil
        # trail synthétique) : une pente de 1,8 % tombe dans le panier
        # PERSONNEL [1.25 %, 3.75 %) mais son point milieu (2.5 %) n'est pas
        # exactement 1,8 % — sans ce snap, `predict_speed` interpolerait entre
        # ce panier et son voisin plat (générique ici) et rendrait "mixed".
        bins_with_range = [
            {"grade_lo": -0.0125, "grade_hi": 0.0125, "grade_mid": 0.0, "speed_ms": 3.0,
             "source": "generic", "ci_low_speed_ms": None, "ci_high_speed_ms": None, "hr_bpm": None},
            {"grade_lo": 0.0125, "grade_hi": 0.0375, "grade_mid": 0.025, "speed_ms": 2.0,
             "source": "personal", "ci_low_speed_ms": 1.9, "ci_high_speed_ms": 2.1, "hr_bpm": 150},
        ]
        seg = [{"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
                "grade_mean_pct": 1.8, "elevation_gain_m": 18.0, "elevation_loss_m": 0.0}]
        out = RP.predict_segments(seg, bins_with_range, fade_pct=0.0, heat_factor=1.0)
        self.assertEqual(out[0]["source"], "personal")
        # Vitesse EXACTEMENT celle du panier personnel (aucune interpolation) :
        # 1000 m / 2.0 m/s = 500 s.
        self.assertEqual(out[0]["predicted_time_s"]["realistic"], 500)

    def test_open_tail_bin_with_none_bounds_is_treated_as_infinite(self):
        # Panier ouvert (queue) réel : `grade_lo`/`grade_hi` valent `None` pour
        # une borne infinie (voir `arc_slope_model.slope_model_bins`), jamais
        # « information absente ».
        bins_with_open_tail = [
            {"grade_lo": None, "grade_hi": -0.0125, "grade_mid": -0.05, "speed_ms": 4.0,
             "source": "personal", "ci_low_speed_ms": 3.8, "ci_high_speed_ms": 4.2, "hr_bpm": 130},
        ]
        seg = [{"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
                "grade_mean_pct": -20.0, "elevation_gain_m": 0.0, "elevation_loss_m": 200.0}]
        out = RP.predict_segments(seg, bins_with_open_tail, fade_pct=0.0, heat_factor=1.0)
        self.assertEqual(out[0]["source"], "personal")
        self.assertEqual(out[0]["predicted_time_s"]["realistic"], 250)  # 1000 / 4.0


# ---------------------------------------------------------------------------
# Altitude manquante (revue de code #59, blocant)
# ---------------------------------------------------------------------------

class TestMissingElevation(unittest.TestCase):
    def test_gpx_without_any_elevation_still_predicts_a_nonzero_plan(self):
        pts = [{"lat": SAFE_LAT, "lon": SAFE_LON + i * (100.0 / M_PER_DEG_LON), "ele": None} for i in range(20)]
        plan = RP.build_race_plan(pts, GENERIC_BINS, start_time="07:00", race_date="2026-11-15", segment_m=500.0)
        self.assertGreater(plan["totals"]["time_s"]["realistic"], 0)
        self.assertTrue(any("altitude" in w.lower() for w in plan["warnings"]))
        for seg in plan["segments"]:
            self.assertEqual(seg["grade_mean_pct"], None)
            self.assertIn("missing_elevation", seg["reason_code"] or "")

    def test_elevation_coverage_pct_helper(self):
        pts_full = [{"ele": 10.0}, {"ele": 20.0}]
        pts_partial = [{"ele": 10.0}, {"ele": None}]
        pts_empty: list = []
        self.assertEqual(RP.elevation_coverage_pct(pts_full), 100.0)
        self.assertEqual(RP.elevation_coverage_pct(pts_partial), 50.0)
        self.assertEqual(RP.elevation_coverage_pct(pts_empty), 100.0)

    def test_partial_missing_elevation_warns_without_failing_the_plan(self):
        pts = _straight_course(_ClimbFlatDescentProfile(), step_m=5.0)
        # La moitié des points perdent leur altitude (un GPX partiellement corrompu).
        for i, p in enumerate(pts):
            if i % 2 == 0:
                p["ele"] = None
        plan = RP.build_race_plan(pts, GENERIC_BINS, start_time="07:00", race_date="2026-11-15", segment_m=500.0)
        self.assertGreater(plan["totals"]["time_s"]["realistic"], 0)
        self.assertTrue(any("altitude manquante" in w.lower() for w in plan["warnings"]))

    def test_missing_elevation_segment_gets_a_note(self):
        seg = [{"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
                "grade_mean_pct": None, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0,
                "_profile": [(1000.0, None)]}]
        out = RP.predict_segments(seg, GENERIC_BINS, fade_pct=0.0, heat_factor=1.0)
        self.assertEqual(out[0]["reason_code"], "missing_elevation")
        self.assertIsNotNone(out[0]["predicted_time_s"]["realistic"])
        self.assertTrue(any("altitude manquante" in n for n in out[0]["notes"]))

    def test_missing_elevation_source_is_never_personal(self):
        # Nit (revue de code #59) : une pente SUPPOSÉE plate (altitude manquante)
        # ne doit jamais s'afficher "personal", même si le modèle a un panier
        # personnel exactement au plat — ce n'est jamais une mesure de terrain.
        seg = [{"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
                "grade_mean_pct": None, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0,
                "_profile": [(1000.0, None)]}]
        out = RP.predict_segments(seg, PERSONAL_BINS, fade_pct=0.0, heat_factor=1.0)
        self.assertEqual(out[0]["source"], "generic")
        self.assertNotEqual(out[0]["source"], "personal")


# ---------------------------------------------------------------------------
# Ravitaillement au-delà de la fin du GPX / rééchelonnage (revue de code #59)
# ---------------------------------------------------------------------------

class TestAidStationBeyondCourseEnd(unittest.TestCase):
    def _segments(self):
        segs = [{"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
                 "grade_mean_pct": 0.0, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0}]
        return RP.predict_segments(segs, GENERIC_BINS, fade_pct=0.0, heat_factor=1.0)

    def test_station_beyond_the_measured_end_is_attached_to_the_finish(self):
        segs = self._segments()
        stations = [{"km": 5.0, "name": "Arrivée théorique"}]  # bien au-delà du dernier segment (1 km)
        passages = RP.compute_passages(segs, stations)
        self.assertEqual(len(passages["aid_station_passages"]), 1)
        entry = passages["aid_station_passages"][0]
        self.assertIn("note", entry)
        self.assertIn("au-delà", entry["note"])
        self.assertEqual(entry["realistic"], passages["segment_passages"][-1]["realistic"])

    def test_rescale_aid_stations_maps_official_km_onto_measured_distance(self):
        stations = [{"km": 10.0, "name": "mi-course"}]
        # GPX mesuré à 9 km pour une course officielle de 10 km -> ratio 0.9.
        rescaled = RP.rescale_aid_stations(stations, measured_total_m=9000.0, official_distance_m=10000.0)
        self.assertAlmostEqual(rescaled[0]["km"], 9.0)
        # Distances manquantes : inchangé.
        self.assertEqual(RP.rescale_aid_stations(stations, None, 10000.0), stations)
        self.assertEqual(RP.rescale_aid_stations(stations, 9000.0, None), stations)


# ---------------------------------------------------------------------------
# Barrières horaires multi-jours (revue de code #59, should-fix)
# ---------------------------------------------------------------------------

class TestCutoffFormats(unittest.TestCase):
    def _passage(self, seconds):
        return [{"km": 10.0, "name": "Ravito", "safe": seconds, "realistic": seconds, "ambitious": seconds}]

    def test_elapsed_format_supports_more_than_24_hours(self):
        start = datetime(2026, 11, 15, 7, 0)
        stations = [{"km": 10.0, "name": "Ravito", "cutoff": "+30:00"}]
        # 29 h de course (104 400 s), barrière à +30 h -> marge positive d'1 h.
        cutoffs = RP.check_cutoffs(self._passage(29 * 3600), stations, start)
        self.assertEqual(cutoffs[0]["realistic"]["margin_s"], 3600)
        self.assertEqual(cutoffs[0]["realistic"]["status"], "ok")

    def test_iso_datetime_expresses_an_absolute_day_two_barrier(self):
        start = datetime(2026, 11, 15, 7, 0)
        stations = [{"km": 10.0, "name": "Ravito", "cutoff": "2026-11-16T10:30:00"}]
        # Passage à +27h30 (98 100 s) = 2026-11-16T10:30:00 pile -> marge nulle.
        cutoffs = RP.check_cutoffs(self._passage(27 * 3600 + 1800), stations, start)
        self.assertEqual(cutoffs[0]["realistic"]["margin_s"], 0)

    def test_cutoff_day_disambiguates_a_same_looking_hhmm_on_day_two(self):
        start = datetime(2026, 11, 15, 7, 0)
        # "10:00" SANS cutoff_day est le jour même (10:00 > 07:00 de départ) :
        # passage à +2h (09:00) -> marge d'1h, "ok".
        stations_day1 = [{"km": 10.0, "name": "Ravito", "cutoff": "10:00"}]
        cutoffs_day1 = RP.check_cutoffs(self._passage(2 * 3600), stations_day1, start)
        self.assertEqual(cutoffs_day1[0]["realistic"]["status"], "ok")
        # "10:00" AVEC cutoff_day=2 : le lendemain 10:00, une marge bien plus
        # généreuse que la barrière du jour même pour le MÊME passage.
        stations_day2 = [{"km": 10.0, "name": "Ravito", "cutoff": "10:00", "cutoff_day": 2}]
        cutoffs_day2 = RP.check_cutoffs(self._passage(2 * 3600), stations_day2, start)
        self.assertGreater(cutoffs_day2[0]["realistic"]["margin_s"], cutoffs_day1[0]["realistic"]["margin_s"])

    def test_unreadable_cutoff_is_ignored_not_raised(self):
        start = datetime(2026, 11, 15, 7, 0)
        stations = [{"km": 10.0, "name": "Ravito", "cutoff": "pas une heure"}]
        self.assertEqual(RP.check_cutoffs(self._passage(3600), stations, start), [])


# ---------------------------------------------------------------------------
# Résolveurs CLI (`_resolve_*`) — conn SQLite en mémoire, sans fichiers réels
# ---------------------------------------------------------------------------

class TestResolvers(unittest.TestCase):
    def _conn(self):
        conn = IDX.open_db(Path(tempfile.gettempdir()) / "arc-race-pacing-tests-nonexistent", None, True, True)
        self.addCleanup(conn.close)
        return conn

    def _conf(self):
        return IDX.settings(IDX.load_config(Path(tempfile.gettempdir()) / "arc-race-pacing-tests-nonexistent"))

    def test_resolve_fade_falls_back_to_generic_without_durability_data(self):
        conn = self._conn()
        fade_pct, source = RP._resolve_fade(conn, date(2026, 9, 27), _Args(fade_pct=None, fade_weeks=None))
        self.assertEqual((fade_pct, source), (RP.DEFAULT_GENERIC_FADE_PCT, "generic"))

    def test_resolve_fade_honours_an_explicit_override(self):
        conn = self._conn()
        fade_pct, source = RP._resolve_fade(conn, date(2026, 9, 27), _Args(fade_pct=3.5, fade_weeks=None))
        self.assertEqual((fade_pct, source), (3.5, "override"))

    def test_resolve_model_bins_empty_workspace(self):
        conn = self._conn()
        bins, flat_ref = RP._resolve_model_bins(conn, self._conf(), _Args(band="endurance", months=None, today=None))
        self.assertEqual(bins, [])
        self.assertIsNone(flat_ref)

    def test_resolve_acclimated_is_none_without_any_session_considered(self):
        # #59, revue de code : AUCUNE séance dans la fenêtre (pas seulement
        # aucune séance chaude) doit rendre `None`, jamais `False`.
        conn = self._conn()
        acclimated, note = RP._resolve_acclimated(conn, self._conf(), date(2026, 9, 27), temp_max_c=30.0)
        self.assertIsNone(acclimated)
        self.assertIsNone(note)

    def test_resolve_acclimated_is_none_below_the_heat_threshold(self):
        conn = self._conn()
        acclimated, note = RP._resolve_acclimated(conn, self._conf(), date(2026, 9, 27), temp_max_c=18.0)
        self.assertIsNone(acclimated)
        self.assertIsNone(note)

    def test_resolve_intensity_factor_without_gpx_distance_stays_at_one(self):
        conn = self._conn()
        factor, source, race_speed, notes = RP._resolve_intensity_factor(conn, {"sport": "trail"}, 3.0, None, None)
        self.assertEqual((factor, source, race_speed, notes), (1.0, "none", None, []))

    def test_resolve_intensity_factor_without_flat_reference_stays_at_one(self):
        conn = self._conn()
        factor, source, race_speed, notes = RP._resolve_intensity_factor(conn, {"sport": "trail"}, None, 10000, 0)
        self.assertEqual((factor, source, race_speed, notes), (1.0, "none", None, []))

    def _insert_activity(self, conn, *, sport, distance_m, duration_s, elevation_gain_m=None, avg_hr_bpm=None,
                          days_ago=10, intensity=None):
        day = (date.today() - timedelta(days=days_ago)).isoformat()
        conn.execute(
            "INSERT INTO activity (source_path, date, sport, distance_m, duration_s, elevation_gain_m, "
            "avg_hr_bpm) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"{day}-{sport}.md", day, sport, distance_m, duration_s, elevation_gain_m, avg_hr_bpm))
        if intensity is not None:
            conn.execute("INSERT INTO planned_session (date, sport, intensity) VALUES (?, ?, ?)",
                         (day, sport, intensity))
        conn.commit()
        return day

    def test_easy_long_run_is_rejected_as_a_reference_falls_back_to_none(self):
        # #59, 2ᵉ revue de code, BLOQUANT : un footing facile, même long, n'est
        # PAS une référence d'allure de course — ni plan dur, ni FC élevée ici.
        conn = self._conn()
        conn.execute("INSERT INTO athlete (hr_max_bpm) VALUES (190)")
        self._insert_activity(conn, sport="trail", distance_m=22000, duration_s=8000, elevation_gain_m=774,
                               avg_hr_bpm=143, intensity="endurance")
        factor, source, race_speed, notes = RP._resolve_intensity_factor(conn, {"sport": "trail"}, 2.9, 10000, 0)
        self.assertEqual((factor, source, race_speed), (1.0, "none", None))

    def test_hard_effort_via_planned_intensity_is_accepted(self):
        conn = self._conn()
        self._insert_activity(conn, sport="running", distance_m=10000, duration_s=2400, intensity="race")
        factor, source, race_speed, notes = RP._resolve_intensity_factor(conn, {"sport": "road"}, 2.9, 10000, 0)
        self.assertEqual(source, "riegel")
        self.assertGreater(factor, 1.0)
        self.assertIsNotNone(race_speed)

    def test_hard_effort_via_high_heart_rate_is_accepted_without_a_plan(self):
        conn = self._conn()
        conn.execute("INSERT INTO athlete (hr_max_bpm) VALUES (190)")  # Z3/Z4 (%FCmax repli) = 152 bpm
        self._insert_activity(conn, sport="running", distance_m=10000, duration_s=2400, avg_hr_bpm=165)
        factor, source, race_speed, notes = RP._resolve_intensity_factor(conn, {"sport": "road"}, 2.9, 10000, 0)
        self.assertEqual(source, "riegel")
        self.assertGreater(factor, 1.0)

    def test_low_heart_rate_without_a_plan_is_rejected(self):
        conn = self._conn()
        conn.execute("INSERT INTO athlete (hr_max_bpm) VALUES (190)")
        self._insert_activity(conn, sport="running", distance_m=10000, duration_s=2400, avg_hr_bpm=140)
        factor, source, race_speed, notes = RP._resolve_intensity_factor(conn, {"sport": "road"}, 2.9, 10000, 0)
        self.assertEqual((factor, source, race_speed), (1.0, "none", None))

    def test_longest_qualifying_hard_effort_is_preferred(self):
        conn = self._conn()
        self._insert_activity(conn, sport="running", distance_m=5000, duration_s=1100, intensity="race",
                               days_ago=20)
        self._insert_activity(conn, sport="running", distance_m=15000, duration_s=3600, intensity="tempo",
                               days_ago=5)
        reference = RP._select_hard_reference(conn, {"sport": "road"})
        self.assertEqual(reference["distance_m"], 15000)

    def test_reference_and_target_elevation_are_both_converted_to_flat_equivalent(self):
        # #59, 2ᵉ revue de code, BLOQUANT : la référence a son PROPRE D+ (200 m
        # sur 10 km) qui doit être converti EXACTEMENT comme la cible, avant
        # d'appeler `arc_metrics.riegel` — jamais un mélange brut/converti qui
        # compterait le relief une seconde fois côté modèle pente -> allure.
        conn = self._conn()
        self._insert_activity(conn, sport="trail", distance_m=10000, duration_s=3000, elevation_gain_m=200,
                               intensity="race")
        flat_reference_speed_ms = 2.9
        factor, source, race_speed, notes = RP._resolve_intensity_factor(
            conn, {"sport": "trail"}, flat_reference_speed_ms, 10000, 0)
        self.assertEqual(source, "riegel")
        expected_reference_flat_m = 10000 + 200 * M.TRAIL_FLAT_M_PER_M_DPLUS
        expected_predicted_s = M.riegel(3000, expected_reference_flat_m, 10000, M.RIEGEL_EXPONENT["trail"])
        expected_race_speed = 10000 / expected_predicted_s
        self.assertAlmostEqual(race_speed, expected_race_speed, places=6)
        self.assertAlmostEqual(factor, expected_race_speed / flat_reference_speed_ms, places=6)

    def test_objective_differing_from_gpx_warns_but_uses_the_gpx(self):
        conn = self._conn()
        conn.execute("INSERT INTO objective (distance_m, elevation_gain_m) VALUES (52000, 2400)")
        self._insert_activity(conn, sport="trail", distance_m=10000, duration_s=2400, intensity="race")
        # GPX réellement analysé : 31 km, bien loin des 52 km de l'objectif (> 10 %).
        factor, source, race_speed, notes = RP._resolve_intensity_factor(conn, {"sport": "trail"}, 2.9, 31000, 912)
        self.assertTrue(any("objectif" in n.lower() and "gpx" in n.lower() for n in notes), notes)

    def test_objective_close_to_gpx_does_not_warn(self):
        conn = self._conn()
        conn.execute("INSERT INTO objective (distance_m, elevation_gain_m) VALUES (10000, 0)")
        self._insert_activity(conn, sport="running", distance_m=10000, duration_s=2400, intensity="race")
        factor, source, race_speed, notes = RP._resolve_intensity_factor(conn, {"sport": "road"}, 2.9, 10100, 0)
        self.assertEqual(notes, [])

    def test_factor_below_one_under_the_clamp_duration_is_clamped_with_a_note(self):
        # Référence plus LENTE en équivalent plat que la référence d'endurance —
        # implausible sur une prédiction courte (< 4h30) : plafonné à 1.0.
        conn = self._conn()
        self._insert_activity(conn, sport="running", distance_m=10000, duration_s=3000, intensity="race")
        factor, source, race_speed, notes = RP._resolve_intensity_factor(conn, {"sport": "road"}, 4.0, 10000, 0)
        self.assertEqual(factor, 1.0)
        self.assertTrue(any("plafonné" in n.lower() for n in notes), notes)

    def test_sweep_of_flat_distances_up_to_marathon_all_faster_than_endurance_pace(self):
        # Repère de non-régression (revue de code #59) : sur un profil PLAT,
        # jusqu'au marathon, l'allure de course mise à l'échelle reste toujours
        # plus RAPIDE que l'allure d'endurance mesurée (facteur > 1), avec une
        # seule référence dure de 10 km.
        conn = self._conn()
        self._insert_activity(conn, sport="running", distance_m=10000, duration_s=2400, intensity="race")
        flat_reference_speed_ms = 2.9
        for distance_m in (5000, 10000, 21097, 42195):
            factor, source, race_speed, notes = RP._resolve_intensity_factor(
                conn, {"sport": "road"}, flat_reference_speed_ms, distance_m, 0)
            self.assertEqual(source, "riegel", distance_m)
            self.assertGreater(factor, 1.0, distance_m)


class _Args:
    """Espace de noms minimal imitant `argparse.Namespace` pour les résolveurs
    CLI — seuls les attributs qu'ils lisent réellement sont fournis."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# ---------------------------------------------------------------------------
# Bout en bout, main-calculé : montée + plat + descente, paniers connus, fade
# et ravitaillement (revue de code #59)
# ---------------------------------------------------------------------------

class TestHandComputedEndToEndPassageTable(unittest.TestCase):
    def test_climb_flat_descent_with_fade_and_aid_station(self):
        # Trois segments construits À LA MAIN (pas de `_profile` : pente
        # uniforme par segment, cas déjà couvert par `_segment_intervals`),
        # paniers PERSONNELS exacts aux points milieux (aucune interpolation).
        segs = [
            {"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0,
             "grade_mean_pct": 10.0, "elevation_gain_m": 100.0, "elevation_loss_m": 0.0},
            {"id": "s02", "km_start": 1.0, "km_end": 2.0, "distance_m": 1000.0,
             "grade_mean_pct": 0.0, "elevation_gain_m": 0.0, "elevation_loss_m": 0.0},
            {"id": "s03", "km_start": 2.0, "km_end": 3.0, "distance_m": 1000.0,
             "grade_mean_pct": -10.0, "elevation_gain_m": 0.0, "elevation_loss_m": 100.0},
        ]
        bins = [
            {"grade_mid": -0.10, "speed_ms": 4.0, "source": "personal",
             "ci_low_speed_ms": 3.8, "ci_high_speed_ms": 4.2, "hr_bpm": 130},
            {"grade_mid": 0.0, "speed_ms": 2.0, "source": "personal",
             "ci_low_speed_ms": 1.9, "ci_high_speed_ms": 2.1, "hr_bpm": 145},
            {"grade_mid": 0.10, "speed_ms": 1.0, "source": "personal",
             "ci_low_speed_ms": 0.9, "ci_high_speed_ms": 1.1, "hr_bpm": 165},
        ]
        # Fade nul, chaleur nulle : temps "realistic" main-calculés = distance / vitesse du panier.
        predicted = RP.predict_segments(segs, bins, fade_pct=0.0, heat_factor=1.0)
        expected_realistic = {"s01": round(1000.0 / 1.0), "s02": round(1000.0 / 2.0), "s03": round(1000.0 / 4.0)}
        for seg in predicted:
            self.assertEqual(seg["predicted_time_s"]["realistic"], expected_realistic[seg["id"]], seg["id"])
            self.assertEqual(seg["source"], "personal")

        stations = [{"km": 1.5, "name": "Ravito du plat", "stop_s": 120.0}]
        passages = RP.compute_passages(predicted, stations)

        # Passage cumulé (realistic) à la fin de s01 = 1000 s (arrondi à la
        # minute la plus proche).
        self.assertEqual(passages["segment_passages"][0]["realistic"], RP._round_passage(1000.0))
        # Ravito au km 1.5 : `compute_passages` ne teste la présence d'un ravito
        # qu'aux BORNES de segment, jamais en cours de segment — la station est
        # donc rattachée à la fin du PREMIER segment dont `km_end` atteint/dépasse
        # son propre km (ici s02, km_end = 2.0 >= 1.5), avec le cumul APRÈS s02
        # en entier : s01 (1000 s) + s02 (500 s) = 1500 s.
        self.assertEqual(passages["aid_station_passages"][0]["realistic"], RP._round_passage(1500.0))
        # Total = s01 (1000) + s02 (500) + arrêt ravito (120) + s03 (250) = 1870 s.
        expected_total = RP._round_passage(1000.0 + 500.0 + 120.0 + 250.0)
        self.assertEqual(passages["totals_s"]["realistic"], expected_total)

        cutoffs = RP.check_cutoffs(passages["aid_station_passages"], stations, datetime(2026, 11, 15, 7, 0))
        self.assertEqual(cutoffs, [])  # pas de `cutoff` déclaré sur cette station.


if __name__ == "__main__":
    unittest.main()
