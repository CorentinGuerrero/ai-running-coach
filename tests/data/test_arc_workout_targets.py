"""Palier D — cibles personnelles d'une séance structurée (#60, épopée #23).

Familles de tests :
- Mapping intensité -> zone FC (`INTENSITY_TO_ZONE`), y compris les intensités
  sans mapping (`race`/`rest`/`strength`).
- `hr_target_for_intensity` : bornes bpm arrondies, méthode utilisée, absence
  de zones -> `reason`/`reason_code` explicite, jamais de bornes inventées.
- Conversions d'unités (`pace_s_km_to_speed_ms`/`speed_ms_to_pace_s_km`) et le
  fait que `flat_pace_target_for_intensity` rend directement des m/s (pas de
  conversion supplémentaire nécessaire côté DTO).
- `flat_pace_target_for_intensity` : cible seulement pour recovery/endurance,
  provenance personnelle vs générique, `reason_code` explicite sinon.
- `hill_repeat_targets` : D+ attendu = vitesse prédite x durée x pente,
  structure invalide, pente non positive -> jamais de D+ négatif présenté
  comme un dénivelé de montée.
- `parse_structure_text` : gabarit français "6×3 min côte 8 %", jamais de
  structure partiellement devinée sur un texte hors gabarit.
- `validate_workout_step_dto` : forme du DTO Garmin (skills/garmin-workout-
  scheduling/SKILL.md) pour un pas HR et un pas d'allure, cas invalides.
- `build_session_targets` : bout en bout, structure -> hill_repeats seul,
  sinon pace_target seul.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import arc_workout_targets as T  # noqa: E402


ATHLETE_KARVONEN = {"hr_max_bpm": 190, "hr_rest_bpm": 50}  # pas de FC au seuil -> Karvonen
# Z2 = [50+0.60*140, 50+0.70*140] = [134, 148] ; Z4 = [50+0.80*140, 50+0.90*140] = [162, 176]

FLAT_BINS = [
    {"grade_mid": -0.10, "speed_ms": 2.5, "source": "personal", "hr_bpm": 145,
     "ci_low_speed_ms": 2.4, "ci_high_speed_ms": 2.6},
    {"grade_mid": 0.0, "speed_ms": 3.0, "source": "personal", "hr_bpm": 140,
     "ci_low_speed_ms": 2.9, "ci_high_speed_ms": 3.1},
    {"grade_mid": 0.08, "speed_ms": 2.0, "source": "generic", "hr_bpm": None,
     "ci_low_speed_ms": None, "ci_high_speed_ms": None},
]


class TestIntensityToZoneMapping(unittest.TestCase):
    def test_mapping_covers_recovery_through_vo2max(self):
        self.assertEqual(T.INTENSITY_TO_ZONE, {
            "recovery": 1, "endurance": 2, "tempo": 3, "threshold": 4, "vo2max": 5,
        })

    def test_race_rest_strength_have_no_zone_mapping(self):
        for intensity in ("race", "rest", "strength"):
            self.assertNotIn(intensity, T.INTENSITY_TO_ZONE)


class TestHrTargetForIntensity(unittest.TestCase):
    def test_endurance_resolves_to_karvonen_zone2_bounds(self):
        result = T.hr_target_for_intensity("endurance", ATHLETE_KARVONEN)
        self.assertEqual(result["bounds_bpm"], [134, 148])
        self.assertEqual(result["zone"], 2)
        self.assertEqual(result["method"], "karvonen")
        self.assertIsNone(result["reason"])
        self.assertIsNone(result["reason_code"])

    def test_threshold_resolves_to_karvonen_zone4_bounds(self):
        result = T.hr_target_for_intensity("threshold", ATHLETE_KARVONEN)
        self.assertEqual(result["bounds_bpm"], [162, 176])
        self.assertEqual(result["zone"], 4)

    def test_bounds_are_rounded_to_int_for_the_dto(self):
        # FC max/repos qui ne tombent pas rond -> bornes arrondies à l'entier.
        athlete = {"hr_max_bpm": 191, "hr_rest_bpm": 47}
        result = T.hr_target_for_intensity("recovery", athlete)
        for bound in result["bounds_bpm"]:
            self.assertIsInstance(bound, int)

    def test_unmapped_intensity_never_fabricates_bounds(self):
        for intensity in ("race", "rest", "strength", "n_importe_quoi"):
            result = T.hr_target_for_intensity(intensity, ATHLETE_KARVONEN)
            self.assertIsNone(result["bounds_bpm"])
            self.assertEqual(result["reason_code"], "unmapped_intensity")
            self.assertIsNotNone(result["reason"])

    def test_missing_profile_data_gives_reason_not_exception(self):
        result = T.hr_target_for_intensity("endurance", {})
        self.assertIsNone(result["bounds_bpm"])
        self.assertEqual(result["reason_code"], "no_zone_data")
        self.assertIsNotNone(result["reason"])
        self.assertEqual(result["zone"], 2)  # la zone visée reste connue même sans bornes

    def test_forced_method_missing_field_gives_explicit_reason(self):
        # LTHR forcé sur un profil qui n'a que FC max/repos -> reason dédiée,
        # jamais un repli silencieux sur Karvonen.
        result = T.hr_target_for_intensity("endurance", ATHLETE_KARVONEN, hr_zones_method="lthr")
        self.assertIsNone(result["bounds_bpm"])
        self.assertEqual(result["reason_code"], "no_zone_data")
        self.assertIn("seuil", result["reason"])


class TestUnitConversions(unittest.TestCase):
    def test_pace_to_speed_and_back_round_trips(self):
        pace = 300.0  # 5 min/km
        speed = T.pace_s_km_to_speed_ms(pace)
        self.assertAlmostEqual(speed, 1000.0 / 300.0)
        self.assertAlmostEqual(T.speed_ms_to_pace_s_km(speed), pace, places=6)

    def test_zero_or_negative_or_none_pace_is_none(self):
        for bad in (0.0, -5.0, None):
            self.assertIsNone(T.pace_s_km_to_speed_ms(bad))
            self.assertIsNone(T.speed_ms_to_pace_s_km(bad))

    def test_flat_pace_target_speeds_are_already_meters_per_second(self):
        # 3.0 m/s = 333.33 s/km : vérifie le sens physique de la conversion,
        # pas seulement l'absence d'exception.
        result = T.flat_pace_target_for_intensity("endurance", FLAT_BINS)
        self.assertAlmostEqual(result["pace_high_s_km"], 1000.0 / result["speed_low_ms"])
        self.assertAlmostEqual(result["pace_low_s_km"], 1000.0 / result["speed_high_ms"])


class TestFlatPaceTargetForIntensity(unittest.TestCase):
    def test_endurance_gets_a_range_around_the_personal_flat_reference(self):
        result = T.flat_pace_target_for_intensity("endurance", FLAT_BINS)
        self.assertEqual(result["source"], "personal")
        self.assertLess(result["speed_low_ms"], 3.0)
        self.assertGreater(result["speed_high_ms"], 3.0)
        self.assertIsNone(result["reason"])

    def test_recovery_also_gets_a_flat_target(self):
        result = T.flat_pace_target_for_intensity("recovery", FLAT_BINS)
        self.assertIsNotNone(result["speed_low_ms"])

    def test_hard_intensities_never_get_a_fabricated_pace_target(self):
        for intensity in ("tempo", "threshold", "vo2max", "race"):
            result = T.flat_pace_target_for_intensity(intensity, FLAT_BINS)
            self.assertIsNone(result["speed_low_ms"])
            self.assertIsNone(result["speed_high_ms"])
            self.assertEqual(result["reason_code"], "no_personal_pace_scaling_for_intensity")

    def test_no_model_gives_reason_not_exception(self):
        result = T.flat_pace_target_for_intensity("endurance", [])
        self.assertIsNone(result["speed_low_ms"])
        self.assertIsNotNone(result["reason_code"])


class TestHillRepeatTargets(unittest.TestCase):
    def test_expected_elevation_gain_is_speed_times_duration_times_grade(self):
        structure = {"reps": 6, "rep_duration_s": 180, "grade_pct": 8}
        result = T.hill_repeat_targets(structure, FLAT_BINS)
        # panier grade_mid=0.08 -> speed_ms=2.0 (générique) : distance = 2.0*180 = 360 m,
        # D+ = 360 * 0.08 = 28.8 m par répétition, x6 = 172.8 m.
        self.assertAlmostEqual(result["per_rep"]["distance_m"], 360.0)
        self.assertAlmostEqual(result["per_rep"]["elevation_gain_m"], 28.8)
        self.assertAlmostEqual(result["total_elevation_gain_m"], 172.8)
        self.assertEqual(result["per_rep"]["source"], "generic")
        self.assertEqual(result["total_work_duration_s"], 1080)

    def test_non_positive_grade_never_yields_a_fabricated_gain(self):
        for grade in (0, -8):
            result = T.hill_repeat_targets({"reps": 6, "rep_duration_s": 180, "grade_pct": grade}, FLAT_BINS)
            self.assertIsNone(result["total_elevation_gain_m"])
            self.assertIsNone(result["per_rep"])
            self.assertEqual(result["reason_code"], "grade_not_positive")

    def test_invalid_structure_gives_reason_not_exception(self):
        for bad in ({"reps": 0, "rep_duration_s": 180, "grade_pct": 8},
                    {"reps": 6, "rep_duration_s": -1, "grade_pct": 8},
                    {"reps": 6, "rep_duration_s": 180, "grade_pct": "huit"},
                    {"reps": 6, "rep_duration_s": 180}):
            result = T.hill_repeat_targets(bad, FLAT_BINS)
            self.assertEqual(result["reason_code"], "invalid_structure")
            self.assertIsNone(result["per_rep"])

    def test_no_model_data_gives_reason_not_exception(self):
        result = T.hill_repeat_targets({"reps": 4, "rep_duration_s": 120, "grade_pct": 10}, [])
        self.assertIsNotNone(result["reason_code"])
        self.assertIsNone(result["total_elevation_gain_m"])


class TestParseStructureText(unittest.TestCase):
    def test_parses_the_canonical_french_phrasing(self):
        result = T.parse_structure_text("6×3 min côte 8 %")
        self.assertEqual(result, {"reps": 6, "rep_duration_s": 180.0, "grade_pct": 8.0})

    def test_parses_ascii_x_and_decimal_comma(self):
        result = T.parse_structure_text("5 x 2,5 min cote a 6,5%")
        self.assertEqual(result["reps"], 5)
        self.assertAlmostEqual(result["rep_duration_s"], 150.0)
        self.assertAlmostEqual(result["grade_pct"], 6.5)

    def test_unmatched_text_returns_none_never_a_partial_guess(self):
        for text in (None, "", "footing tranquille 45 min", "6 fractions de 3 min"):
            self.assertIsNone(T.parse_structure_text(text))


class TestValidateWorkoutStepDto(unittest.TestCase):
    def test_valid_hr_step_has_no_errors(self):
        step = T.dto_hr_step(1, description="Z2", duration_s=2700, bounds_bpm=[134, 148])
        self.assertEqual(T.validate_workout_step_dto(step), [])

    def test_valid_pace_step_has_no_errors(self):
        step = T.dto_pace_step(1, description="plat", duration_s=1200,
                                speed_low_ms=2.8, speed_high_ms=3.2)
        self.assertEqual(T.validate_workout_step_dto(step), [])

    def test_pace_step_with_inverted_bounds_is_rejected(self):
        step = T.dto_pace_step(1, description="plat", duration_s=1200,
                                speed_low_ms=3.2, speed_high_ms=2.8)
        errors = T.validate_workout_step_dto(step)
        self.assertTrue(any("targetValueOne" in e for e in errors))

    def test_hr_step_with_both_zone_number_and_custom_range_is_rejected(self):
        step = T.dto_hr_step(1, description="Z2", duration_s=2700, bounds_bpm=[134, 148])
        step["zoneNumber"] = 2
        errors = T.validate_workout_step_dto(step)
        self.assertTrue(errors)

    def test_unknown_step_type_id_is_rejected(self):
        step = T.dto_hr_step(1, description="Z2", duration_s=2700, bounds_bpm=[134, 148])
        step["stepType"] = {"stepTypeId": 99, "stepTypeKey": "interval"}
        errors = T.validate_workout_step_dto(step)
        self.assertTrue(any("stepTypeId" in e for e in errors))

    def test_missing_end_condition_value_is_rejected_unless_lap_button(self):
        step = T.dto_hr_step(1, description="Z2", duration_s=2700, bounds_bpm=[134, 148])
        del step["endConditionValue"]
        self.assertTrue(T.validate_workout_step_dto(step))
        step["endCondition"] = {"conditionTypeId": 1, "conditionTypeKey": "lap.button"}
        self.assertEqual(T.validate_workout_step_dto(step), [])


class TestBuildSessionTargets(unittest.TestCase):
    def test_flat_session_gets_hr_and_pace_targets_no_hill_repeats(self):
        session = {"date": "2026-09-30", "sport": "trail", "title": "Footing", "intensity": "endurance"}
        result = T.build_session_targets(session, athlete=ATHLETE_KARVONEN, bins=FLAT_BINS)
        self.assertIsNone(result["hill_repeats"])
        self.assertEqual(result["hr_target"]["bounds_bpm"], [134, 148])
        self.assertIsNotNone(result["pace_target"]["speed_low_ms"])

    def test_hill_session_gets_hill_repeats_no_pace_target(self):
        session = {
            "date": "2026-09-30", "sport": "trail", "title": "Côtes", "intensity": "vo2max",
            "structure": {"reps": 6, "rep_duration_s": 180, "grade_pct": 8},
        }
        result = T.build_session_targets(session, athlete=ATHLETE_KARVONEN, bins=FLAT_BINS)
        self.assertIsNone(result["pace_target"])
        self.assertIsNotNone(result["hill_repeats"]["total_elevation_gain_m"])
        self.assertEqual(result["hr_target"]["bounds_bpm"], [176, 190])  # Z5


if __name__ == "__main__":
    unittest.main()
