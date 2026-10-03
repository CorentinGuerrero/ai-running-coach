"""Palier D — projection de charge sur le bloc (#172, `scripts/arc_load_forecast.py`).

Historique synthétique + semaines planifiées → projections connues. Le test de référence recalcule la
projection À LA MAIN avec `arc_metrics.daily_series` et `arc_guardrails.projected_session_load` (jamais un
second modèle) ; un autre vérifie la cohérence avec l'ACWR projeté de R1 (`_project_series`).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import arc_guardrails as G  # noqa: E402
import arc_index as I  # noqa: E402
import arc_load_forecast as LF  # noqa: E402
import arc_metrics as M  # noqa: E402

TODAY = date(2026, 9, 21)            # lundi
RACE = "2026-10-11"                  # dimanche, trois semaines plus tard
HISTORY_START = date(2026, 3, 1)


def history(daily=40.0, end=TODAY, start=HISTORY_START):
    out, day = {}, start
    while day < end:
        out[day.isoformat()] = daily
        day += timedelta(days=1)
    return out


def sess(day, intensity="endurance", minutes=60, **extra):
    return {"date": day, "sport": "trail", "title": "séance", "intensity": intensity,
            "planned_duration_s": minutes * 60, **extra}


def plan(week_start, sessions):
    return {"week_start": week_start, "sessions": sessions}


def build_block(weeks_minutes):
    """Trois semaines : `weeks_minutes[i]` = minutes d'endurance chaque jour de la semaine i."""
    weeks = []
    for i, minutes in enumerate(weeks_minutes):
        start = TODAY + timedelta(days=7 * i)
        weeks.append(plan(start.isoformat(), [sess((start + timedelta(days=d)).isoformat(), minutes=minutes)
                                              for d in range(7)]))
    return weeks


class TestForecast(unittest.TestCase):
    def test_matches_manual_daily_series(self):
        weeks = build_block([60, 60, 30])
        result = LF.forecast(history(), TODAY, RACE, None, weeks)
        self.assertEqual(result["status"], "ok")
        loads = history()
        for week in weeks:
            for s in week["sessions"]:
                loads[s["date"]] = G.projected_session_load(s)
        expected = {p["date"]: p for p in M.daily_series(loads, HISTORY_START, date.fromisoformat(RACE))}[RACE]
        self.assertEqual(result["race_day"]["date"], RACE)
        self.assertEqual(result["race_day"]["form"], expected["form"])
        self.assertEqual(result["race_day"]["fitness"], expected["fitness"])
        self.assertEqual(result["race_day"]["fatigue"], expected["fatigue"])
        self.assertTrue(result["is_estimate"])
        self.assertEqual(result["weeks_planned"], 3)
        self.assertEqual(result["weeks_unplanned"], 0)

    def test_taper_gives_fresher_race_day_than_no_taper(self):
        heavy = LF.forecast(history(), TODAY, RACE, None, build_block([90, 90, 90]))
        taper = LF.forecast(history(), TODAY, RACE, None, build_block([90, 90, 30]))
        self.assertGreater(taper["race_day"]["form"], heavy["race_day"]["form"])

    def test_peak_fatigue_week_and_series_flags(self):
        result = LF.forecast(history(), TODAY, RACE, None, build_block([60, 120, 30]))
        # La charge la plus lourde est en semaine 2 : la fatigue culmine en fin de semaine 2 (dimanche).
        self.assertEqual(result["peak_fatigue"]["week_start"], (TODAY + timedelta(days=7)).isoformat())
        projected = [p for p in result["series"] if p["projected"]]
        self.assertEqual(projected[0]["date"], TODAY.isoformat())
        self.assertEqual(projected[-1]["date"], RACE)
        self.assertFalse(result["series"][0]["projected"])     # point d'ancrage réel (veille)

    def test_consistent_with_r1_projection(self):
        """L'ACWR par semaine reprend EXACTEMENT la projection de R1 pour la première semaine à venir."""
        weeks = build_block([75, 60, 30])
        result = LF.forecast(history(), TODAY, RACE, None, weeks)
        ctx = {"today": TODAY.isoformat(), "loads_by_date": history(), "week_activities": [],
               "recent_run_pace_s_km": None}
        r1 = G._project_series(ctx, weeks[0]["sessions"], TODAY, TODAY + timedelta(days=6))
        self.assertIsNotNone(r1["acwr_projected"])
        self.assertEqual(result["weeks"][0]["acwr_max"], r1["acwr_projected"])
        # Même charge de séance que R1 : total de la semaine 0 = somme des charges projetées.
        self.assertAlmostEqual(result["weeks"][0]["load_total"],
                               round(sum(G.projected_session_load(s) for s in weeks[0]["sessions"]), 2), places=1)

    def test_unplanned_weeks_are_counted_and_zero_load(self):
        weeks = build_block([60])                    # semaines 2 et 3 non planifiées
        result = LF.forecast(history(), TODAY, RACE, None, weeks)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["weeks_planned"], 1)
        self.assertEqual(result["weeks_unplanned"], 2)
        self.assertEqual(result["unplanned_week_starts"],
                         [(TODAY + timedelta(days=7)).isoformat(), (TODAY + timedelta(days=14)).isoformat()])
        self.assertTrue(result["partial_plan"])
        later = [p for p in result["series"] if p["date"] >= (TODAY + timedelta(days=7)).isoformat()]
        self.assertTrue(all(p["load"] == 0 for p in later))

    def test_excluded_sessions_weigh_nothing(self):
        week = plan(TODAY.isoformat(), [sess("2026-09-22", status="cancelled"), sess("2026-09-23", intensity="rest"),
                                        sess("2026-09-24")])
        result = LF.forecast(history(), TODAY, "2026-09-27", None, [week])
        by_day = {p["date"]: p["load"] for p in result["series"]}
        self.assertEqual(by_day["2026-09-22"], 0)
        self.assertEqual(by_day["2026-09-23"], 0)
        self.assertGreater(by_day["2026-09-24"], 0)

    def test_real_activity_today_is_not_counted_twice(self):
        week = plan(TODAY.isoformat(), [sess(TODAY.isoformat(), intensity="vo2max", minutes=60)])
        acts = [{"date": TODAY.isoformat(), "sport": "trail", "load": 55.0}]
        result = LF.forecast(history(), TODAY, "2026-09-27", None, [week], acts)
        today_point = next(p for p in result["series"] if p["date"] == TODAY.isoformat())
        self.assertEqual(today_point["load"], 55.0)   # réel (apparié), pas réel + projeté

    def test_distance_only_session_uses_recent_pace_and_is_flagged(self):
        s = {"date": "2026-09-23", "sport": "trail", "intensity": "endurance", "planned_distance_m": 10000}
        with_pace = LF.forecast(history(), TODAY, "2026-09-27", None, [plan(TODAY.isoformat(), [s])],
                                recent_pace_s_km=360.0)
        self.assertGreater(next(p for p in with_pace["series"] if p["date"] == "2026-09-23")["load"], 0)
        self.assertEqual(with_pace["estimated_duration_dates"], ["2026-09-23"])
        no_pace = LF.forecast(history(), TODAY, "2026-09-27", None, [plan(TODAY.isoformat(), [s])])
        self.assertEqual(no_pace["unresolved_duration_dates"], ["2026-09-23"])

    def test_honest_states(self):
        self.assertEqual(LF.forecast(history(), TODAY, None, None, build_block([60]))["status"], "no_objective")
        self.assertEqual(LF.forecast(history(), TODAY, "2026-09-01", None, build_block([60]))["status"], "target_past")
        self.assertEqual(LF.forecast(history(), TODAY, RACE, None, [])["status"], "no_plan")
        short = history(start=TODAY - timedelta(days=G.MIN_HISTORY_DAYS_FOR_PROJECTION - 1))
        insufficient = LF.forecast(short, TODAY, RACE, None, build_block([60, 60, 60]))
        self.assertEqual(insufficient["status"], "insufficient_history")
        self.assertNotIn("race_day", insufficient)
        self.assertEqual(LF.forecast({}, TODAY, RACE, None, build_block([60]))["status"], "insufficient_history")

    def test_history_floor_is_exactly_r1s(self):
        ok = history(start=TODAY - timedelta(days=G.MIN_HISTORY_DAYS_FOR_PROJECTION))
        self.assertEqual(LF.forecast(ok, TODAY, RACE, None, build_block([60]))["status"], "ok")

    def test_until_overrides_and_race_beyond_gives_no_race_day(self):
        until = TODAY + timedelta(days=6)
        result = LF.forecast(history(), TODAY, RACE, until, build_block([60]))
        self.assertEqual(result["target_date"], until.isoformat())
        self.assertIsNone(result["race_day"])
        self.assertEqual(result["end"]["date"], until.isoformat())

    def test_vocabulary_is_generic(self):
        text = json.dumps(LF.forecast(history(), TODAY, RACE, None, build_block([60]))) + M.ASSUMPTIONS["load_forecast"]
        self.assertIsNone(re.search(r"\b(CTL|ATL|TSB|TSS)\b", text))
        self.assertIn("estimation", M.ASSUMPTIONS["load_forecast"].lower())


class TestCompare(unittest.TestCase):
    def test_deltas_between_current_and_taper_variant(self):
        current = build_block([90, 90, 90])
        taper_week3 = [plan((TODAY + timedelta(days=14)).isoformat(),
                            [sess("2026-10-06", minutes=30), sess("2026-10-08", minutes=20)])]
        out = LF.compare(history(), TODAY, RACE, None, current, taper_week3)
        self.assertEqual(out["replaced_weeks"], [(TODAY + timedelta(days=14)).isoformat()])
        self.assertEqual(out["added_weeks"], [])
        d = out["deltas"]
        self.assertGreater(d["race_day_form"], 0)
        self.assertLess(d["planned_load_total"], 0)
        self.assertLess(d["peak_fatigue"], 0.01)
        cur, alt = out["current"]["race_day"]["form"], out["alternative"]["race_day"]["form"]
        self.assertAlmostEqual(d["race_day_form"], alt - cur, places=2)
        self.assertIn("plus fraîche", out["reading"])
        # Le plan actuel n'est pas muté par la comparaison.
        self.assertEqual(len(current[2]["sessions"]), 7)

    def test_added_week_and_non_ok_state(self):
        out = LF.compare(history(), TODAY, RACE, None, build_block([60]), build_block([60, 60]))
        self.assertEqual(out["added_weeks"], [(TODAY + timedelta(days=7)).isoformat()])
        none = LF.compare(history(), TODAY, None, None, build_block([60]), build_block([30]))
        self.assertIsNone(none["deltas"])
        self.assertEqual(none["current"]["status"], "no_objective")

    def test_alternative_weeks_from_block(self):
        self.assertEqual(len(LF.alternative_weeks_from_block({"week_start": "2026-10-05", "sessions": []})), 1)
        self.assertEqual(len(LF.alternative_weeks_from_block({"weeks": [{"week_start": "2026-10-05"}]})), 1)
        with self.assertRaises(ValueError):
            LF.alternative_weeks_from_block({"foo": 1})


class TestFromIndexAndCli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="arc-load-forecast-"))
        self.ws = self.tmp / "ws"
        for d in ("activities", "medical", "nutrition", "planning", "rapports"):
            (self.ws / d).mkdir(parents=True)
        # Historique : une séance toutes les 3 j sur ~130 jours (charge sRPE sans FC).
        day = TODAY - timedelta(days=130)
        while day < TODAY:
            self._write(f"activities/{day.isoformat()}_trail.md",
                        {"kind": "activity", "date": day.isoformat(), "sport": "trail", "duration_s": 3600,
                         "distance_m": 9000, "elevation_gain_m": 200, "rpe": 5})
            day += timedelta(days=3)
        (self.ws / "planning/active_objective.md").write_text(
            "# Objectif actif\n\n## Course visée\n\n"
            f"- **Nom** : Trail X\n- **Date** : {RACE}\n- **Distance** : 40 km\n", encoding="utf-8")
        for i, minutes in enumerate((60, 60, 30)):
            start = TODAY + timedelta(days=7 * i)
            self._write(f"planning/{start.isoformat()}_semaine.md", {
                "kind": "week", "week_start": start.isoformat(), "location": "Tournai",
                "sessions": [sess((start + timedelta(days=d)).isoformat(), minutes=minutes) for d in (1, 3, 5)]})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, rel, data):
        text = f"# Titre\n\n```arc\n{json.dumps({'arc': 1, **data}, ensure_ascii=False)}\n```\n\nTexte.\n"
        (self.ws / rel).write_text(text, encoding="utf-8")

    def _cli(self, *args):
        proc = subprocess.run([sys.executable, str(REPO / "scripts" / "arc_index.py"), "load-forecast",
                               "--workspace", str(self.ws), "--today", TODAY.isoformat(), *args],
                              capture_output=True, text=True, timeout=120)
        return proc

    def test_cli_json_ok(self):
        proc = self._cli("--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["race_date"], RACE)
        self.assertEqual(data["weeks_planned"], 3)
        self.assertIsNotNone(data["race_day"]["form"])

    def test_cli_text_and_until_error(self):
        proc = self._cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Forme prévue le jour J", proc.stdout)
        self.assertIn("pas une mesure", proc.stdout)
        bad = self._cli("--until", "pas-une-date")
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("--until", bad.stderr)

    def test_cli_compare_week_file(self):
        alt = self.tmp / "taper.json"
        alt.write_text(json.dumps({"week_start": (TODAY + timedelta(days=14)).isoformat(),
                                   "sessions": [sess("2026-10-07", minutes=20)]}), encoding="utf-8")
        proc = self._cli("--json", "--compare", str(alt))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["replaced_weeks"], [(TODAY + timedelta(days=14)).isoformat()])
        self.assertGreater(data["deltas"]["race_day_form"], 0)
        missing = self._cli("--compare", str(self.tmp / "absent.json"))
        self.assertNotEqual(missing.returncode, 0)

    def test_index_function_matches_pure_function(self):
        conn = I.open_db(self.ws, memory=True)
        try:
            I.index_workspace(conn, self.ws, TODAY.isoformat())
            report = I.load_forecast(conn, TODAY)
            self.assertEqual(report["status"], "ok")
            direct = LF.load_forecast(conn, TODAY)
            self.assertEqual(report["race_day"], direct["race_day"])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
