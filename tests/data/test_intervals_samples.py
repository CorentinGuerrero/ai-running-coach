"""Palier D — échantillons FIT d'une séance synchronisée depuis Intervals.icu (#68).

Une séance `[data].source = "intervals"` porte un `intervals_activity_id` (chaîne
`i<chiffres>`) au lieu d'un `garmin_activity_id` (entier). Son FIT, téléchargé par
`skills/fit-download/scripts/download_fit.py --source intervals`, est normalisé au
même chemin canonique `activities/fit/<id>.json` — ici `activities/fit/i123.json`.

Critère central (`TestParityWithGarmin`) : les MÊMES échantillons donnent
EXACTEMENT les mêmes KPI (zones, GAP, découplage, VAM, descente, durabilité,
dépense énergétique) qu'ils soient rattachés à un identifiant Garmin ou
Intervals.icu — seul l'identifiant change, jamais le calcul.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
import arc_climb_match as VM  # noqa: E402
import arc_index as I  # noqa: E402
import arc_samples as S  # noqa: E402
from tests.lib.synthetic import sample_session  # noqa: E402

INTERVALS_ID = "i123456789"
GARMIN_ID = 90000000068

# Colonnes KPI de `activity` calculées depuis les échantillons (#43-#48, énergie).
KPI_COLUMNS = ("gap_pace_s_km", "decoupling_pct", "ef_whole", "best_climb_vam_elapsed_m_h",
               "best_vam_10min_m_h", "descent_reference_gap_pace_s_km", "durability_gap_fade_pct", "durability_ef_fade_pct")


def _arc(data: dict) -> str:
    return f"# Séance\n\n```arc\n{json.dumps(data)}\n```\n\nTexte du coach.\n"


def _hilly_records() -> list:
    """Séance d'1 h 40 à vérité connue : une montée puis une descente marquées
    (VAM, descente), une dérive cardiaque (découplage) et un fade (durabilité)."""
    records, _truth = sample_session(
        seed=68, duration_s=6000, segments=((2000.0, 1500.0, 9.0), (4000.0, 1500.0, -9.0)),
        decoupling_pct=4.0, fade_pct=5.0)
    return records


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="arc-intervals-"))
        self.ws = self.tmp / "ws"
        for d in ("activities", "medical", "nutrition", "planning", "rapports"):
            (self.ws / d).mkdir(parents=True)
        self.conn = I.open_db(self.ws, memory=True)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel: str, text: str) -> None:
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def index(self, today="2026-09-30"):
        return I.index_workspace(self.conn, self.ws, today)

    def write_profile(self):
        self.write("planning/Runner_Profile.md",
                   "# Profil\n\n## Physiologie\n\n- **FC max** : 185\n- **FC de repos de référence** : 50\n"
                   "- **Poids de forme** : 70 kg\n")

    def write_activity(self, day="2026-09-29", *, intervals_id=INTERVALS_ID, garmin_id=None,
                       duration_s=6000, distance_m=15000, sport="trail"):
        data = {"arc": 1, "kind": "activity", "date": day, "sport": sport,
                "duration_s": duration_s, "distance_m": distance_m}
        if garmin_id is not None:
            data["garmin_activity_id"] = garmin_id
        if intervals_id is not None:
            data["intervals_activity_id"] = intervals_id
        self.write(f"activities/{day}_{sport}.md", _arc(data))

    def write_fit(self, activity_id, records, filename=None):
        self.write(f"activities/fit/{filename or activity_id}.json",
                   json.dumps({"activity_id": activity_id, "records": records}))

    def activity(self, col, value):
        return self.conn.execute(f"SELECT * FROM activity WHERE {col} = ?", (value,)).fetchone()

    def cli(self, *argv) -> dict:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = I.main([*argv, "--workspace", str(self.ws), "--memory", "--today", "2026-09-30"])
        self.assertEqual(code, 0)
        return json.loads(out.getvalue().strip().splitlines()[-1])


class TestActivityRef(unittest.TestCase):
    def test_parse_activity_ref_accepts_both_id_spaces_only(self):
        self.assertEqual(S.parse_activity_ref("24070286912"), 24070286912)
        self.assertEqual(S.parse_activity_ref(24070286912), 24070286912)
        self.assertEqual(S.parse_activity_ref("i123456789"), "i123456789")
        for bad in ("", "i", "abc", "123456789i", "I123", None, True, 1.5):
            self.assertIsNone(S.parse_activity_ref(bad), bad)

    def test_file_name_carries_the_intervals_id(self):
        self.assertEqual(S.sample_file_activity_id(Path("activities/fit/i123456789.json")), "i123456789")
        self.assertEqual(S.sample_file_activity_id(Path("activities/fit/123.json")), 123)
        self.assertIsNone(S.sample_file_activity_id(Path("activities/fit/notes.json")))

    def test_activity_ref_prefers_garmin_then_intervals(self):
        self.assertEqual(I.activity_ref({"garmin_activity_id": 5, "intervals_activity_id": "i9"}), 5)
        self.assertEqual(I.activity_ref({"garmin_activity_id": None, "intervals_activity_id": "i9"}), "i9")
        self.assertIsNone(I.activity_ref({"garmin_activity_id": None, "intervals_activity_id": None}))
        self.assertIsNone(I.activity_ref({"intervals_activity_id": "pas-un-id"}))

    def test_climb_segment_seed_never_collides_and_stays_js_safe(self):
        self.assertEqual(VM.segment_seed(24070286912), 24070286912)
        seed = VM.segment_seed("i123456789")
        self.assertEqual(seed, VM.INTERVALS_SEED_OFFSET + 123456789)
        self.assertGreater(seed, 10 ** 11, "au-delà de tout identifiant Garmin réaliste")
        self.assertLess(seed * VM.SEGMENT_ID_CLIMB_MULTIPLIER + 9999, 2 ** 53,
                        "Number.MAX_SAFE_INTEGER : le tableau de bord (JS) manipule cet id")


class TestIntervalsSampleIngestion(Workspace):
    def _records(self, n=20):
        return [{"t_s": float(t), "distance_m": t * 2.5, "altitude_m": 500.0, "hr_bpm": 140.0,
                 "speed_ms": 2.5, "cadence_spm": 160.0} for t in range(n)]

    def test_intervals_file_links_to_its_activity(self):
        self.write_activity()
        self.write_fit(INTERVALS_ID, self._records())
        counts = self.index()
        self.assertEqual(counts["fit_ingestion"]["ingested"], 1)
        row = self.activity("intervals_activity_id", INTERVALS_ID)
        self.assertEqual(len(I.samples(self.conn, row["id"])), 4)   # 20 s -> 4 buckets de 5 s
        stored = self.conn.execute(
            "SELECT DISTINCT garmin_activity_id, intervals_activity_id FROM activity_sample").fetchall()
        self.assertEqual([tuple(r) for r in stored], [(None, INTERVALS_ID)])

    def test_json_activity_id_is_the_fallback_for_a_renamed_file(self):
        self.write_activity()
        self.write_fit(INTERVALS_ID, self._records(), filename="copie-a-la-main")
        self.index()
        self.assertEqual(len(I.samples_by_ref(self.conn, INTERVALS_ID)["samples"]), 4)

    def test_file_without_any_valid_id_is_invalid_not_ingested(self):
        self.write_fit("pas-un-id", self._records(), filename="notes")
        counts = self.index()
        self.assertEqual(counts["fit_ingestion"]["invalid"], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM activity_sample").fetchone()[0], 0)

    def test_fit_before_markdown_is_not_lost(self):
        self.write_fit(INTERVALS_ID, self._records())
        self.index()
        self.assertEqual(I.sample_coverage(self.conn)["unlinked_garmin_ids"], 1)
        self.write_activity()
        self.index()
        coverage = I.sample_coverage(self.conn)
        self.assertEqual((coverage["activities_with_samples"], coverage["unlinked_garmin_ids"]), (1, 0))

    def test_deleted_file_removes_its_samples(self):
        self.write_activity()
        self.write_fit(INTERVALS_ID, self._records())
        self.index()
        (self.ws / f"activities/fit/{INTERVALS_ID}.json").unlink()
        self.assertEqual(self.index()["fit_ingestion"]["removed"], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM activity_sample").fetchone()[0], 0)

    def test_same_intervals_id_in_two_files_is_counted_once(self):
        self.write_activity("2026-09-29")
        self.write_activity("2026-09-28")
        self.index()
        n = self.conn.execute(
            "SELECT COUNT(*) FROM activity WHERE intervals_activity_id = ?", (INTERVALS_ID,)).fetchone()[0]
        self.assertEqual(n, 1)

    def test_cli_samples_accepts_intervals_id(self):
        self.write_activity()
        self.write_fit(INTERVALS_ID, self._records())
        out = self.cli("samples", INTERVALS_ID)
        self.assertEqual(out["intervals_activity_id"], INTERVALS_ID)
        self.assertNotIn("garmin_activity_id", out)
        self.assertEqual(len(out["samples"]), 4)

    def test_cli_rejects_an_unknown_id_form(self):
        with self.assertRaises(I.ConfigError) as cm:
            I.main(["gap", "--activity", "x123", "--workspace", str(self.ws), "--memory"])
        self.assertIn("i<chiffres>", str(cm.exception))


class TestParityWithGarmin(Workspace):
    """Mêmes échantillons, deux séances identiques — l'une Garmin, l'autre
    Intervals.icu : chaque KPI dérivé doit être strictement égal."""

    def setUp(self):
        super().setUp()
        records = _hilly_records()
        self.write_profile()
        self.write_activity("2026-09-28", intervals_id=None, garmin_id=GARMIN_ID)
        self.write_activity("2026-09-29", intervals_id=INTERVALS_ID)
        self.write_fit(GARMIN_ID, records)
        self.write_fit(INTERVALS_ID, records)
        self.index()
        self.garmin = self.activity("garmin_activity_id", GARMIN_ID)
        self.intervals = self.activity("intervals_activity_id", INTERVALS_ID)

    def test_every_kpi_column_matches(self):
        for col in KPI_COLUMNS:
            with self.subTest(col=col):
                self.assertEqual(self.intervals[col], self.garmin[col])
        # Garde-fou : la parité ne doit pas être celle de deux `None`.
        self.assertIsNotNone(self.intervals["gap_pace_s_km"])
        self.assertIsNotNone(self.intervals["best_climb_vam_elapsed_m_h"])
        self.assertIsNotNone(self.intervals["decoupling_pct"])

    def test_zone_time_matches(self):
        def zones(act_id):
            return dict(self.conn.execute(
                "SELECT zone, seconds FROM hr_zone_time WHERE activity_id = ?", (act_id,)).fetchall())
        self.assertTrue(zones(self.intervals["id"]))
        self.assertEqual(zones(self.intervals["id"]), zones(self.garmin["id"]))

    def test_energy_model_matches(self):
        def kcal(act_id):
            return self.conn.execute(
                "SELECT model_kcal FROM activity_energy WHERE activity_id = ?", (act_id,)).fetchone()[0]
        self.assertIsNotNone(kcal(self.intervals["id"]))
        self.assertEqual(kcal(self.intervals["id"]), kcal(self.garmin["id"]))

    def test_intervals_climb_is_matched_to_a_segment(self):
        segments = [r[0] for r in self.conn.execute(
            "SELECT segment_id FROM activity_climb WHERE activity_id = ? AND segment_id IS NOT NULL",
            (self.intervals["id"],))]
        self.assertTrue(segments)

    def test_every_per_activity_report_accepts_the_intervals_id(self):
        conf = I.settings(I.load_config(self.ws))
        reports = {
            "zones": I.activity_zone_report(self.conn, conf, INTERVALS_ID),
            "gap": I.activity_gap_report(self.conn, INTERVALS_ID),
            "decoupling": I.activity_decoupling_report(self.conn, INTERVALS_ID),
            "vam": I.activity_climb_report(self.conn, INTERVALS_ID),
            "descent": I.activity_descent_report(self.conn, INTERVALS_ID),
            "durability": I.activity_durability_report(self.conn, INTERVALS_ID),
        }
        for name, report in reports.items():
            with self.subTest(report=name):
                self.assertEqual(report["intervals_activity_id"], INTERVALS_ID)
                self.assertNotIn("garmin_activity_id", report)
                self.assertNotEqual(report.get("reason_code"), "unknown_activity")
        self.assertEqual(reports["gap"]["gap_pace_s_km"], self.garmin["gap_pace_s_km"])
        energy = I.energy_report(self.conn, activity=INTERVALS_ID)["sessions"][0]
        self.assertIsNotNone(energy["model_kcal"])

    def test_cli_reports_accept_the_intervals_id(self):
        for command in ("gap", "decoupling", "vam", "descent", "durability", "energy", "zones"):
            with self.subTest(command=command):
                out = self.cli(command, "--activity", INTERVALS_ID)
                self.assertNotEqual(out.get("reason_code"), "unknown_activity")

    def test_unknown_intervals_id_names_the_right_key(self):
        report = I.activity_gap_report(self.conn, "i1")
        self.assertEqual(report["reason_code"], "unknown_activity")
        self.assertIn("intervals_activity_id", report["reason"])


class TestClimbSegmentOfAnIntervalsOnlyHistory(Workspace):
    def test_first_seen_segment_id_derives_from_the_intervals_seed(self):
        self.write_activity()
        self.write_fit(INTERVALS_ID, _hilly_records())
        self.index()
        row = self.activity("intervals_activity_id", INTERVALS_ID)
        seg = self.conn.execute(
            "SELECT segment_id FROM activity_climb WHERE activity_id = ? ORDER BY segment_id LIMIT 1",
            (row["id"],)).fetchone()[0]
        self.assertEqual(seg, VM.segment_seed(INTERVALS_ID) * VM.SEGMENT_ID_CLIMB_MULTIPLIER + 1)


class TestEnergyReasonCodes(Workspace):
    def test_intervals_activity_without_fit_is_no_samples(self):
        """Avant ce correctif, une séance Intervals.icu était `no_garmin_id` (« n'a
        jamais pu avoir de FIT ») : elle peut désormais en avoir un, son absence est
        un simple téléchargement manquant."""
        self.write_profile()
        self.write_activity()
        self.index()
        session = I.energy_report(self.conn)["sessions"][0]
        self.assertEqual(session["reason_code"], "no_samples")

    def test_activity_without_any_external_id_is_no_activity_id(self):
        self.write_profile()
        self.write_activity(intervals_id=None)
        self.index()
        session = I.energy_report(self.conn)["sessions"][0]
        self.assertEqual(session["reason_code"], "no_activity_id")


if __name__ == "__main__":
    unittest.main()
