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

import json
import sys
import tempfile
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

    def test_hill_structure_recognized_from_title_when_no_structure_key(self):
        # #107 revue de code, point 7 : le contrat `arc` n'a pas de clé
        # `structure` — une séance lue depuis une vraie semaine ne l'a jamais.
        session = {"date": "2026-10-02", "sport": "trail", "title": "Côtes 6x3 min côte 8%",
                   "intensity": "vo2max"}
        result = T.build_session_targets(session, athlete=ATHLETE_KARVONEN, bins=FLAT_BINS)
        self.assertIsNone(result["pace_target"])
        self.assertIsNotNone(result["hill_repeats"])
        self.assertEqual(result["hill_repeats"]["reps"], 6)
        self.assertEqual(result["hill_repeats"]["grade_pct"], 8.0)

    def test_hill_structure_from_explicit_structure_text_overrides_title(self):
        session = {"date": "2026-10-02", "sport": "trail", "title": "Séance du jour", "intensity": "vo2max"}
        result = T.build_session_targets(session, athlete=ATHLETE_KARVONEN, bins=FLAT_BINS,
                                          structure_text="4x2 min côte 10%")
        self.assertIsNotNone(result["hill_repeats"])
        self.assertEqual(result["hill_repeats"]["reps"], 4)
        self.assertEqual(result["hill_repeats"]["grade_pct"], 10.0)

    def test_flat_session_title_never_misparsed_as_hill(self):
        session = {"date": "2026-10-02", "sport": "trail", "title": "Footing endurance 45 min",
                   "intensity": "endurance"}
        result = T.build_session_targets(session, athlete=ATHLETE_KARVONEN, bins=FLAT_BINS)
        self.assertIsNone(result["hill_repeats"])
        self.assertIsNotNone(result["pace_target"])


class TestOpenEndedZoneClamping(unittest.TestCase):
    """#107 revue de code, point 3 : les zones Z1/Z5 des méthodes LTHR et
    %FCmax sont des SENTINELLES ouvertes (0 bpm / 150 % de LTHR-ou-FCmax),
    jamais une vraie borne physiologique — Karvonen n'a pas ce problème."""

    ATHLETE_LTHR_ONLY = {"hr_threshold_bpm": 170}  # ni hr_rest_bpm ni hr_max_bpm
    ATHLETE_LTHR_FULL = {"hr_threshold_bpm": 170, "hr_rest_bpm": 45, "hr_max_bpm": 195}
    ATHLETE_PCTMAX_ONLY = {"hr_max_bpm": 190}  # pas de hr_rest_bpm

    def test_lthr_zone1_without_hr_rest_gives_reason_not_a_zero_bpm_floor(self):
        result = T.hr_target_for_intensity("recovery", self.ATHLETE_LTHR_ONLY)
        self.assertIsNone(result["bounds_bpm"])
        self.assertEqual(result["reason_code"], "open_zone_floor_unknown")
        self.assertEqual(result["method"], "lthr")

    def test_lthr_zone5_without_hr_max_gives_reason_not_a_150pct_ceiling(self):
        result = T.hr_target_for_intensity("vo2max", self.ATHLETE_LTHR_ONLY)
        self.assertIsNone(result["bounds_bpm"])
        self.assertEqual(result["reason_code"], "open_zone_ceiling_unknown")

    def test_lthr_zone1_floor_uses_hr_rest_bpm_when_known(self):
        result = T.hr_target_for_intensity("recovery", self.ATHLETE_LTHR_FULL)
        self.assertEqual(result["bounds_bpm"][0], 45)  # hr_rest_bpm, jamais 0
        self.assertIsNone(result["reason_code"])

    def test_lthr_zone5_high_clamped_to_hr_max_bpm(self):
        result = T.hr_target_for_intensity("vo2max", self.ATHLETE_LTHR_FULL)
        # Sans clamp : 170 * 1.5 = 255 bpm (implausible) ; avec clamp : 195 (hr_max_bpm).
        self.assertEqual(result["bounds_bpm"][1], 195)
        self.assertIsNone(result["reason_code"])

    def test_percent_max_zone1_without_hr_rest_gives_reason(self):
        result = T.hr_target_for_intensity("recovery", self.ATHLETE_PCTMAX_ONLY)
        self.assertIsNone(result["bounds_bpm"])
        self.assertEqual(result["reason_code"], "open_zone_floor_unknown")

    def test_percent_max_zone5_clamped_to_hr_max_bpm(self):
        result = T.hr_target_for_intensity("vo2max", self.ATHLETE_PCTMAX_ONLY)
        # Sans clamp : 190 * 1.5 = 285 bpm (implausible) ; avec clamp : 190.
        self.assertEqual(result["bounds_bpm"][1], 190)

    def test_karvonen_zone1_and_zone5_are_never_clamped(self):
        athlete = {"hr_max_bpm": 190, "hr_rest_bpm": 50}
        z1 = T.hr_target_for_intensity("recovery", athlete)
        z5 = T.hr_target_for_intensity("vo2max", athlete)
        # Bornes Karvonen réelles (0,50/0,60 et 0,90/1,00 de la réserve) : ni 0 ni 285.
        self.assertEqual(z1["bounds_bpm"], [120, 134])
        self.assertEqual(z5["bounds_bpm"], [176, 190])

    def test_middle_zones_are_never_open_ended_even_with_lthr(self):
        # Z2/Z3/Z4 n'ont jamais de sentinelle à clamper, quelle que soit la méthode.
        result = T.hr_target_for_intensity("tempo", self.ATHLETE_LTHR_ONLY)
        self.assertIsNotNone(result["bounds_bpm"])
        self.assertIsNone(result["reason_code"])


class TestHillRepeatBasis(unittest.TestCase):
    def test_endurance_band_basis_is_a_lower_bound(self):
        result = T.hill_repeat_targets({"reps": 6, "rep_duration_s": 180, "grade_pct": 8}, FLAT_BINS,
                                        band="endurance")
        self.assertEqual(result["basis"], "endurance_pace_lower_bound")

    def test_all_band_basis_is_mixed_effort(self):
        result = T.hill_repeat_targets({"reps": 6, "rep_duration_s": 180, "grade_pct": 8}, FLAT_BINS, band="all")
        self.assertEqual(result["basis"], "mixed_effort_estimate")

    def test_basis_present_even_on_invalid_structure(self):
        result = T.hill_repeat_targets({"reps": 0, "rep_duration_s": 180, "grade_pct": 8}, FLAT_BINS)
        self.assertEqual(result["basis"], "endurance_pace_lower_bound")

    def test_extrapolated_is_surfaced_at_top_level_and_is_not_a_failure(self):
        # Pente bien au-delà du panier extrême le plus proche -> extrapolation
        # informative (#107 revue de code, point 5) : la valeur reste utilisable.
        result = T.hill_repeat_targets({"reps": 4, "rep_duration_s": 120, "grade_pct": 20}, FLAT_BINS)
        self.assertEqual(result["reason_code"], "extrapolated")
        self.assertIsNotNone(result["per_rep"])
        self.assertIsNotNone(result["total_elevation_gain_m"])
        self.assertEqual(result["per_rep"]["reason_code"], "extrapolated")


class TestParseStructureTextHardening(unittest.TestCase):
    """#107 revue de code, point 4."""

    def test_hr_percentage_is_never_mistaken_for_a_grade(self):
        for text in ("6x3 min à 85 % FCmax", "6x3min côte a 85% FCmax", "6x3min côte a 85%FCM"):
            self.assertIsNone(T.parse_structure_text(text), text)

    def test_vma_percentage_is_never_mistaken_for_a_grade(self):
        for text in ("a 90% VMA", "6x3min côte a 90% VMA"):
            self.assertIsNone(T.parse_structure_text(text), text)

    def test_implausibly_steep_grade_is_rejected(self):
        self.assertIsNone(T.parse_structure_text("6x3min côte 45%"))
        self.assertIsNone(T.parse_structure_text("6x3min côte 100%"))

    def test_plausible_grade_at_the_cap_is_accepted(self):
        result = T.parse_structure_text("6x3min côte 40%")
        self.assertEqual(result["grade_pct"], 40.0)

    def test_minutes_seconds_concatenated_notation(self):
        result = T.parse_structure_text("6x1min30 côte 8%")
        self.assertEqual(result["rep_duration_s"], 90.0)  # PAS 60.0 (bug corrigé)

    def test_apostrophe_minutes_notation(self):
        result = T.parse_structure_text("6x3' côte 8%")
        self.assertEqual(result["rep_duration_s"], 180.0)

    def test_bare_seconds_notation(self):
        result = T.parse_structure_text("6x90s côte 8%")
        self.assertEqual(result["rep_duration_s"], 90.0)

    def test_seconde_word_notation(self):
        result = T.parse_structure_text("6x30 sec côte 8%")
        self.assertEqual(result["rep_duration_s"], 30.0)

    def test_anchors_to_the_reps_x_duration_closest_before_cote(self):
        # #107 revue de code, 2ᵉ tour, should-fix : deux blocs dans le même
        # texte (un tempo plat, puis des répétitifs de côte) — le PREMIER
        # "reps x durée" du texte (2x20 min, le tempo) ne doit PAS être
        # confondu avec celui qui décrit réellement la côte (6x1 min).
        result = T.parse_structure_text("2x20 min tempo, puis 6x1 min côte 8%")
        self.assertEqual(result, {"reps": 6, "rep_duration_s": 60.0, "grade_pct": 8.0})

    def test_a_reps_x_duration_group_after_the_climb_mention_is_never_used(self):
        # Aucun "reps x durée" valide AVANT la côte -> None, jamais une
        # structure devinée depuis un groupe qui suit la mention de la pente.
        self.assertIsNone(T.parse_structure_text("côte 8% suivie de 6x1 min de récupération"))

    def test_multiple_climb_blocks_anchor_to_the_nearest_preceding_group_each_time(self):
        result = T.parse_structure_text("4x3 min côte 5%, puis 8x30 sec côte 12%")
        # La pente retenue est la PREMIÈRE trouvée par le gabarit "côte" (5 %) ;
        # le "reps x durée" retenu est le dernier AVANT cette occurrence-là (4x3 min).
        self.assertEqual(result, {"reps": 4, "rep_duration_s": 180.0, "grade_pct": 5.0})


class TestValidateWorkoutStepDtoHrRangeOrdering(unittest.TestCase):
    def test_inverted_hr_custom_range_is_rejected(self):
        step = T.dto_hr_step(1, description="Z2", duration_s=2700, bounds_bpm=[134, 148])
        step["targetValueOne"], step["targetValueTwo"] = step["targetValueTwo"], step["targetValueOne"]
        errors = T.validate_workout_step_dto(step)
        self.assertTrue(any("targetValueOne" in e for e in errors), errors)


class TestLoadSessionArg(unittest.TestCase):
    """`arc_workout_targets._load_session_arg` — #107 revue de code, points 2 et nit."""

    def _week_file(self, tmp: Path, sessions: list) -> Path:
        path = Path(tmp) / "Semaine.md"
        block = {"arc": 1, "kind": "week", "week_start": "2026-09-28", "location": "Tournai",
                 "sessions": sessions}
        path.write_text("# Semaine\n\n```arc\n" + json.dumps(block, ensure_ascii=False) + "\n```\n",
                         encoding="utf-8")
        return path

    def test_json_inline_parsed_directly(self):
        session = T._load_session_arg('{"date": "2026-09-30", "intensity": "endurance"}', Path("."))
        self.assertEqual(session["intensity"], "endurance")

    def test_json_inline_with_hash_in_a_field_is_still_json(self):
        # Nit de la revue #107 : une valeur qui COMMENCE par '{' est du JSON,
        # même si elle contient un '#' ailleurs (ex. dans un titre).
        session = T._load_session_arg(
            '{"date": "2026-09-30", "title": "Séance #3", "intensity": "endurance"}', Path("."))
        self.assertEqual(session["title"], "Séance #3")

    def test_single_session_at_date_is_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._week_file(tmp, [{"date": "2026-09-30", "sport": "trail", "title": "Footing"}])
            session = T._load_session_arg(f"{path}#2026-09-30", Path(tmp))
            self.assertEqual(session["title"], "Footing")

    def test_missing_date_raises_with_explicit_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._week_file(tmp, [{"date": "2026-09-30", "sport": "trail", "title": "Footing"}])
            with self.assertRaises(ValueError):
                T._load_session_arg(f"{path}#2026-10-05", Path(tmp))

    def test_ambiguous_date_without_qualifier_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._week_file(tmp, [
                {"date": "2026-09-30", "sport": "trail", "title": "Seuil", "status": "done"},
                {"date": "2026-09-30", "sport": "trail", "title": "Endurance", "status": "planned"},
            ])
            with self.assertRaises(ValueError):
                T._load_session_arg(f"{path}#2026-09-30", Path(tmp))

    def test_ambiguous_date_resolved_by_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._week_file(tmp, [
                {"date": "2026-09-30", "sport": "trail", "title": "Seuil", "status": "done"},
                {"date": "2026-09-30", "sport": "trail", "title": "Endurance", "status": "planned"},
            ])
            session = T._load_session_arg(f"{path}#2026-09-30@1", Path(tmp))
            self.assertEqual(session["title"], "Endurance")

    def test_ambiguous_date_resolved_by_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._week_file(tmp, [
                {"date": "2026-09-30", "sport": "trail", "title": "Seuil", "status": "done"},
                {"date": "2026-09-30", "sport": "trail", "title": "Endurance", "status": "planned"},
            ])
            session = T._load_session_arg(f"{path}#2026-09-30:Endurance", Path(tmp))
            self.assertEqual(session["status"], "planned")

    def test_index_out_of_range_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._week_file(tmp, [{"date": "2026-09-30", "sport": "trail", "title": "Footing"}])
            with self.assertRaises(ValueError):
                T._load_session_arg(f"{path}#2026-09-30@5", Path(tmp))

    def test_invalid_selector_syntax_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._week_file(tmp, [{"date": "2026-09-30", "sport": "trail", "title": "Footing"}])
            with self.assertRaises(ValueError):
                T._load_session_arg(f"{path}#not-a-date", Path(tmp))

    # -- #69 : fichier plan multi-semaines (`weeks[]`) ------------------------

    def _multi_week_file(self, tmp: Path, weeks: list) -> Path:
        path = Path(tmp) / "Semaine.md"
        block = {"arc": 1, "kind": "week", "weeks": weeks}
        path.write_text("# Semaine\n\n```arc\n" + json.dumps(block, ensure_ascii=False) + "\n```\n",
                         encoding="utf-8")
        return path

    def test_session_found_across_weeks_of_a_multi_week_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._multi_week_file(tmp, [
                {"week_start": "2026-09-21", "location": "Tournai",
                 "sessions": [{"date": "2026-09-22", "sport": "trail", "title": "Footing S1"}]},
                {"week_start": "2026-09-28", "location": "Tournai",
                 "sessions": [{"date": "2026-09-30", "sport": "trail", "title": "Footing S2"}]},
            ])
            session = T._load_session_arg(f"{path}#2026-09-30", Path(tmp))
            self.assertEqual(session["title"], "Footing S2")

    def test_session_not_found_in_any_week_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._multi_week_file(tmp, [
                {"week_start": "2026-09-21", "location": "Tournai",
                 "sessions": [{"date": "2026-09-22", "sport": "trail", "title": "Footing"}]},
            ])
            with self.assertRaises(ValueError):
                T._load_session_arg(f"{path}#2026-10-05", Path(tmp))

    def test_ambiguous_date_across_weeks_resolved_by_title(self):
        """Une date en double n'arrive normalement pas ENTRE deux semaines
        distinctes (#69, chaque semaine couvre 7 jours disjoints) — mais le
        sélecteur `:titre`/`@index` reste utilisable si ça se produisait quand
        même (fichier mal formé, deux `week_start` en collision non résolue ici :
        cette fonction lit le texte brut, pas la table indexée)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._multi_week_file(tmp, [
                {"week_start": "2026-09-21", "location": "Tournai",
                 "sessions": [{"date": "2026-09-22", "sport": "trail", "title": "Seuil"}]},
                {"week_start": "2026-09-21", "location": "Tournai",
                 "sessions": [{"date": "2026-09-22", "sport": "trail", "title": "Endurance"}]},
            ])
            session = T._load_session_arg(f"{path}#2026-09-22:Endurance", Path(tmp))
            self.assertEqual(session["title"], "Endurance")


class TestMainCli(unittest.TestCase):
    """`arc_workout_targets.main` bout en bout, workspace jetable (#107 revue
    de code : couverture explicite demandée pour `main`/`_load_session_arg`)."""

    def _workspace(self, tmp: Path) -> Path:
        ws = Path(tmp)
        (ws / "planning").mkdir(parents=True)
        (ws / "planning" / "Runner_Profile.md").write_text(
            "# Profil de l'athlète\n\n## Physiologie\n\n"
            "- **FC max** : 190\n- **FC de repos de référence** : 50\n", encoding="utf-8")
        return ws

    def test_main_with_json_session_prints_targets(self):
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._workspace(tmp)
            out = io.StringIO()
            with redirect_stdout(out):
                code = T.main(["targets", "--session",
                                '{"date": "2026-09-30", "sport": "trail", "title": "Footing", '
                                '"intensity": "endurance"}',
                                "--workspace", str(ws), "--memory"])
            self.assertEqual(code, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result["hr_target"]["bounds_bpm"], [134, 148])

    def test_main_reports_error_on_missing_session_date(self):
        import io
        from contextlib import redirect_stderr
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._workspace(tmp)
            (ws / "planning" / "Semaine.md").write_text(
                '# Semaine\n\n```arc\n{"arc": 1, "kind": "week", "week_start": "2026-09-28", '
                '"location": "Tournai", "sessions": [{"date": "2026-09-30", "sport": "trail", '
                '"title": "Footing"}]}\n```\n', encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err):
                code = T.main(["targets", "--session", "planning/Semaine.md#2026-10-05",
                                "--workspace", str(ws), "--memory"])
            self.assertEqual(code, 1)
            self.assertIn("aucune séance datée", err.getvalue())


if __name__ == "__main__":
    unittest.main()
