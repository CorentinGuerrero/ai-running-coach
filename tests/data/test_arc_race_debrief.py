"""Palier D — débrief post-course : plan vs réalisé, par segment (#61, épopée #23).

Fixture minimale : un plan à 2 segments (0-2 km / 2-4 km, allure réaliste 300 s/km
sur chaque, soit 600 s/segment) et une activité à splits kilométriques (4 splits
de 1 km chacun) construits pour représenter, selon le cas, une course conforme au
plan, un départ trop rapide suivi d'un fade, ou une distance totale légèrement
différente (mésalignement GPS).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import arc_race_debrief as D  # noqa: E402


def _plan():
    """4 segments d'1 km, allure planifiée constante 300 s/km (scénario réaliste)
    — même granularité que les splits de l'activité fixture, pour que le
    « premier tiers » (#61, `FAST_START_FRACTION`) recouvre au moins un
    segment entier."""
    segments = []
    for i in range(4):
        segments.append({
            "id": f"s0{i + 1}", "km_start": float(i), "km_end": float(i + 1), "distance_m": 1000.0,
            "predicted_time_s": {"safe": 330, "realistic": 300, "ambitious": 275},
            "pace_s_km": {"safe": 330, "realistic": 300, "ambitious": 275},
        })
    return {
        "arc": 1, "kind": "race_plan", "date": "2026-09-20", "race_name": "Trail Fictif",
        "race_date": "2026-09-27",
        "segments": segments,
        "aid_stations": [{"km": 2.0, "name": "Ravito central"}],
    }


def _activity(splits, *, carbs_g=None, duration_s=None):
    data = {
        "arc": 1, "kind": "activity", "date": "2026-09-27", "sport": "trail",
        "duration_s": duration_s if duration_s is not None else sum(s[1] for s in splits),
        "splits_cols": ["km", "duration_s"],
        "splits": [[k, d] for k, d in splits],
    }
    if carbs_g is not None:
        data["carbs_g"] = carbs_g
    return data


class TestBuildActualCheckpoints(unittest.TestCase):
    def test_on_plan_checkpoints(self):
        activity = _activity([(1, 300), (2, 300), (3, 300), (4, 300)])
        checkpoints = D.build_actual_checkpoints(activity)
        self.assertEqual(checkpoints[0], (0.0, 0.0))
        self.assertEqual(checkpoints[-1], (4000.0, 1200.0))

    def test_missing_duration_raises(self):
        activity = {"splits_cols": ["km", "duration_s"], "splits": [[1, None]]}
        with self.assertRaises(D.DebriefError):
            D.build_actual_checkpoints(activity)

    def test_no_splits_raises(self):
        with self.assertRaises(D.DebriefError):
            D.build_actual_checkpoints({"splits_cols": [], "splits": []})


class TestOnPlan(unittest.TestCase):
    """Course courue exactement à l'allure planifiée (600 s/segment) : deltas nuls."""

    def test_zero_delta_and_no_findings_beyond_info(self):
        plan = _plan()
        activity = _activity([(1, 300), (2, 300), (3, 300), (4, 300)])
        result = D.build_race_debrief(plan, activity)
        self.assertEqual(len(result["segments"]), 4)
        for seg in result["segments"]:
            self.assertAlmostEqual(seg["delta_s"], 0.0, places=1)
            self.assertAlmostEqual(seg["delta_pct"], 0.0, places=1)
        self.assertAlmostEqual(result["totals"]["delta_pct"], 0.0, places=1)
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("ecart_temps_total", codes)
        self.assertNotIn("depart_trop_rapide", codes)

    def test_segment_ids_cited(self):
        plan = _plan()
        activity = _activity([(1, 300), (2, 300), (3, 300), (4, 300)])
        result = D.build_race_debrief(plan, activity)
        ids = [s["id"] for s in result["segments"]]
        self.assertEqual(ids, ["s01", "s02", "s03", "s04"])


class TestFastStartFade(unittest.TestCase):
    """Premier segment couru bien plus vite que prévu (240 s/km au lieu de 300),
    second bien plus lentement (400 s/km) : départ trop rapide + fade net."""

    def test_fast_start_finding_fires(self):
        plan = _plan()
        activity = _activity([(1, 220), (2, 220), (3, 420), (4, 420)])
        result = D.build_race_debrief(plan, activity)
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("depart_trop_rapide", codes)
        self.assertTrue(any(u["rationale"] == "depart_trop_rapide" for u in result["suggested_profile_updates"]))
        # Premiers segments nettement plus rapides que le plan, derniers nettement plus lents.
        self.assertLess(result["segments"][0]["delta_pct"], 0)
        self.assertGreater(result["segments"][-1]["delta_pct"], 0)
        self.assertIn("fade", result)
        self.assertGreater(result["fade"]["vs_plan_pct"], 0)

    def test_no_finding_without_fade(self):
        """Un léger écart d'allure sans fade réel ne doit pas déclencher le drapeau."""
        plan = _plan()
        # Allure quasi identique au plan sur les deux segments : pas de fade.
        activity = _activity([(1, 300), (2, 300), (3, 300), (4, 300)])
        result = D.build_race_debrief(plan, activity)
        codes = [f["code"] for f in result["findings"]]
        self.assertNotIn("depart_trop_rapide", codes)


class TestDistanceMismatch(unittest.TestCase):
    """L'activité mesure 4.2 km pour un plan à 4 km (mésalignement GPS) : les
    splits sont mis à l'échelle proportionnellement, jamais le temps."""

    def test_scaling_applied_and_warned(self):
        plan = _plan()
        # 4 splits de 1050 m (donc 4200 m mesurés) à allure constante 300 s/km réel.
        activity = _activity([(1, 315), (2, 315), (3, 315), (4, 315)])
        activity["splits_cols"] = ["km", "duration_s", "distance_m"]
        activity["splits"] = [[k, 315, 1050.0] for k in (1, 2, 3, 4)]
        result = D.build_race_debrief(plan, activity)
        self.assertAlmostEqual(result["alignment"]["actual_distance_m"], 4200.0, places=1)
        self.assertAlmostEqual(result["alignment"]["plan_distance_m"], 4000.0, places=1)
        self.assertGreater(result["alignment"]["mismatch_pct"], 3.0)
        self.assertTrue(any("mis à l'échelle" in w for w in result["warnings"]))
        # Le watch a mesuré 1050 m par km réel (5 % de plus que le plan) : une
        # fois les distances cumulées mises à l'échelle sur le total du plan
        # (jamais le temps), le même temps (315 s) se retrouve réparti sur un
        # kilomètre plus court côté plan -> une allure ~5 % plus lente que
        # celle du plan (300 s/km), cohérent avec l'écart de distance mesuré.
        for seg in result["segments"]:
            self.assertAlmostEqual(seg["delta_pct"], 5.0, delta=1.0)

    def test_no_warning_within_tolerance(self):
        plan = _plan()
        activity = _activity([(1, 300), (2, 300), (3, 300), (4, 300)])
        result = D.build_race_debrief(plan, activity)
        self.assertEqual(result["warnings"], [])


class TestMissingNutritionAndWeather(unittest.TestCase):
    def test_carbs_and_weather_omitted_when_absent(self):
        plan = _plan()
        activity = _activity([(1, 300), (2, 300), (3, 300), (4, 300)])
        result = D.build_race_debrief(plan, activity)
        self.assertNotIn("carbs", result)
        self.assertNotIn("weather", result)
        self.assertNotIn("aid_station_times", result)

    def test_carbs_from_activity_when_long_enough(self):
        plan = _plan()
        # Durée totale > 90 min (LONG_RUN_MIN_DURATION_S) pour que
        # arc_metrics.carbs_per_hour_g rende une valeur.
        activity = _activity([(1, 1400), (2, 1400), (3, 1400), (4, 1400)], carbs_g=100)
        result = D.build_race_debrief(plan, activity, carbs_target_g_h=70.0)
        self.assertIn("carbs", result)
        self.assertIn("actual_g_h", result["carbs"])
        self.assertEqual(result["carbs"]["planned_g_h"], 70.0)

    def test_carbs_under_target_finding(self):
        plan = _plan()
        activity = _activity([(1, 1400), (2, 1400), (3, 1400), (4, 1400)], carbs_g=40)
        result = D.build_race_debrief(plan, activity, carbs_target_g_h=80.0)
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("glucides_sous_objectif", codes)

    def test_weather_both_present(self):
        plan = _plan()
        activity = _activity([(1, 300), (2, 300), (3, 300), (4, 300)])
        planned = {"arc": 1, "kind": "weather", "date": "2026-09-20", "location": "X",
                   "category": "green", "temp_max_c": 18.0}
        actual = {"arc": 1, "kind": "weather", "date": "2026-09-27", "location": "X",
                  "category": "orange", "temp_max_c": 29.0}
        result = D.build_race_debrief(plan, activity, planned_weather=planned, actual_weather=actual)
        self.assertEqual(result["weather"]["planned"]["temp_max_c"], 18.0)
        self.assertEqual(result["weather"]["actual"]["temp_max_c"], 29.0)


class TestNoPlan(unittest.TestCase):
    def test_missing_segments_raises_clear_error(self):
        plan = {"arc": 1, "kind": "race_plan", "date": "2026-09-20", "race_name": "X", "race_date": "2026-09-27"}
        activity = _activity([(1, 300)])
        with self.assertRaises(D.DebriefError) as ctx:
            D.build_race_debrief(plan, activity)
        self.assertIn("segments", str(ctx.exception))

    def test_load_block_missing_file(self):
        with self.assertRaises(D.DebriefError):
            D.load_block(Path("/nonexistent/plan.md"), expected_kind="race_plan")

    def test_load_block_wrong_kind(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f.md"
            path.write_text('# T\n\n```arc\n{"arc": 1, "kind": "activity", "date": "2026-09-20", '
                             '"sport": "trail", "duration_s": 10}\n```\n', encoding="utf-8")
            with self.assertRaises(D.DebriefError):
                D.load_block(path, expected_kind="race_plan")


class TestAidStationTimes(unittest.TestCase):
    def test_stop_detected_near_station(self):
        plan_aid = [{"km": 2.0, "name": "Ravito"}]
        samples = [
            {"t_s": 0, "distance_m": 0.0, "speed_ms": 3.0},
            {"t_s": 10, "distance_m": 1900.0, "speed_ms": 3.0},
            {"t_s": 20, "distance_m": 2000.0, "speed_ms": 0.1},
            {"t_s": 50, "distance_m": 2000.0, "speed_ms": 0.1},
            {"t_s": 60, "distance_m": 2005.0, "speed_ms": 3.0},
        ]
        result = D.aid_station_times(plan_aid, samples)
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(result[0]["actual_stop_s"], 20.0)

    def test_no_stop_near_station_omitted(self):
        plan_aid = [{"km": 2.0, "name": "Ravito"}]
        samples = [{"t_s": t, "distance_m": t * 100.0, "speed_ms": 3.0} for t in range(0, 40, 10)]
        result = D.aid_station_times(plan_aid, samples)
        self.assertEqual(result, [])

    def test_fit_key_absent_without_arg(self):
        plan = _plan()
        activity = _activity([(1, 300), (2, 300), (3, 300), (4, 300)])
        result = D.build_race_debrief(plan, activity, fit_samples=None)
        self.assertNotIn("aid_station_times", result)


if __name__ == "__main__":
    unittest.main()
