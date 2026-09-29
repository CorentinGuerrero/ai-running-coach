"""Palier D — inspection photo des chaussures (#135) : contrat `gear_inspection`, index,
CLI `inspections` / `gear-career`, rappel « inspection conseillée », bilan de carrière,
et sécurité de la route qui sert les photos.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import arc_contract as C  # noqa: E402
import arc_index as I  # noqa: E402
import arc_metrics as M  # noqa: E402
import arc_serve as S  # noqa: E402

TODAY = "2026-09-23"
PHOTO = "gear/photos/2026-09-20_pegasus_semelles.jpg"


def block(**overrides) -> dict:
    data = {"arc": 1, "kind": "gear_inspection", "date": "2026-09-20", "gear_id": "pegasus",
            "condition": "yellow"}
    data.update(overrides)
    return data


def arc_md(data: dict) -> str:
    return f"# Inspection\n\n```arc\n{json.dumps(data, ensure_ascii=False)}\n```\n\nTexte du coach.\n"


class TestContract(unittest.TestCase):
    def check(self, data):
        return C.validate(data)

    def test_minimal_block_is_valid(self):
        self.assertEqual(self.check(block()), ([], []))

    def test_full_block_is_valid(self):
        data = block(distance_m=412000, wear_zones=[{"side": "left", "zone": "heel_posterolateral",
                                                      "severity": "moderate"},
                                                     {"side": "right", "zone": "heel_medial"}],
                     asymmetry={"level": "mild", "side": "left"}, gait_hints=["heel_strike", "pronation_hint"],
                     photos=[PHOTO], previous="gear/2026-08-02_pegasus_inspection.md",
                     scale_reference=True, lug_depth_mm=2.5)
        self.assertEqual(self.check(data), ([], []))

    def test_required_keys(self):
        for key in ("date", "gear_id", "condition"):
            data = block()
            del data[key]
            errors, _ = self.check(data)
            self.assertTrue(any(key in e for e in errors), (key, errors))

    def test_condition_and_enums_are_closed(self):
        self.assertTrue(self.check(block(condition="amber"))[0])
        self.assertTrue(self.check(block(wear_zones=[{"side": "front", "zone": "toe"}]))[0])
        self.assertTrue(self.check(block(wear_zones=[{"side": "left", "zone": "sole"}]))[0])
        self.assertTrue(self.check(block(gait_hints=["overpronator"]))[0])
        self.assertTrue(self.check(block(gait_hints="heel_strike"))[0])
        self.assertTrue(self.check(block(asymmetry={"level": "huge"}))[0])

    def test_gear_id_must_be_a_slug(self):
        self.assertTrue(self.check(block(gear_id="Nike Pegasus"))[0])

    def test_no_mm_measure_without_scale_reference(self):
        errors, _ = self.check(block(lug_depth_mm=3.0))
        self.assertTrue(any("scale_reference" in e for e in errors), errors)
        errors, _ = self.check(block(lug_depth_mm=3.0, scale_reference=False))
        self.assertTrue(any("scale_reference" in e for e in errors), errors)
        self.assertEqual(self.check(block(lug_depth_mm=3.0, scale_reference=True)), ([], []))

    def test_implausible_lug_depth_warns(self):
        _, warnings = self.check(block(lug_depth_mm=40, scale_reference=True))
        self.assertTrue(any("lug_depth_mm" in w for w in warnings), warnings)

    def test_asymmetry_side_required_when_asymmetric(self):
        for level in ("mild", "marked"):
            errors, _ = self.check(block(asymmetry={"level": level}))
            self.assertTrue(any("asymmetry.side" in e for e in errors), (level, errors))
        self.assertEqual(self.check(block(asymmetry={"level": "none"})), ([], []))
        _, warnings = self.check(block(asymmetry={"level": "none", "side": "left"}))
        self.assertTrue(any("ignoré" in w for w in warnings), warnings)

    def test_single_sole_documented_warns(self):
        _, warnings = self.check(block(wear_zones=[{"side": "left", "zone": "toe"}]))
        self.assertTrue(any("DEUX" in w for w in warnings), warnings)

    def test_photo_paths_are_confined_to_gear_photos(self):
        bad = ["../secret.jpg", "gear/photos/../../planning/Runner_Profile.md", "/etc/passwd.jpg",
               "planning/x.jpg", "gear/x.jpg", "gear/photos/a.svg", "gear/photos/a.md",
               "gear\\photos\\a.jpg", "gear/photos/C:/a.jpg", "https://evil.example/a.jpg", "~/a.jpg",
               "gear/photos//a.jpg"]
        for path in bad:
            errors, _ = self.check(block(photos=[path]))
            self.assertTrue(errors, f"chemin accepté à tort : {path}")
        for good in ("gear/photos/a.jpg", "gear/photos/a.JPEG", "gear/photos/2026/b.png", "gear/photos/c.webp"):
            self.assertEqual(self.check(block(photos=[good])), ([], []), good)
        self.assertTrue(self.check(block(photos="gear/photos/a.jpg"))[0])

    def test_previous_must_be_an_inspection_file(self):
        self.assertTrue(self.check(block(previous="planning/Runner_Profile.md"))[0])
        self.assertTrue(self.check(block(previous="gear/../x_inspection.md"))[0])
        self.assertEqual(self.check(block(previous="gear/2026-08-02_pegasus_inspection.md")), ([], []))

    def test_unknown_key_is_a_warning(self):
        errors, warnings = self.check(block(diagnosis="pronation sévère"))
        self.assertEqual(errors, [])
        self.assertTrue(any("diagnosis" in w for w in warnings), warnings)

    def test_folder_mapping(self):
        self.assertEqual(C.KIND_FOLDERS["gear_inspection"], "gear")
        self.assertIn("gear_inspection", C.KINDS)


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="arc-inspection-"))
        self.ws = self.tmp / "ws"
        for d in ("activities", "medical", "nutrition", "planning", "rapports", "gear/photos"):
            (self.ws / d).mkdir(parents=True)
        self.conn = I.open_db(self.ws, memory=True)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel: str, text: str) -> None:
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def profile(self, bullets: str) -> None:
        self.write("planning/Runner_Profile.md",
                   f"# Profil\n\n## Matériel & lieux\n\n### Chaussures\n\n{bullets}\n")

    def activity(self, day: str, distance_m: float = 10000, gear_id: str = None, sport: str = "trail",
                 splits: bool = False) -> None:
        data = {"arc": 1, "kind": "activity", "date": day, "sport": sport, "duration_s": 3600,
                "distance_m": distance_m}
        if gear_id:
            data["gear_id"] = gear_id
        if splits:
            data["splits_cols"] = ["km", "duration_s"]
            data["splits"] = [[k + 1, 300 + k] for k in range(int(distance_m // 1000))]
        self.write(f"activities/{day}_{sport}.md", arc_md(data))

    def inspection(self, day: str, gear_id: str = "pegasus", **overrides) -> None:
        self.write(f"gear/{day}_{gear_id}_inspection.md",
                   arc_md(block(date=day, gear_id=gear_id, **overrides)))

    def index(self):
        return I.index_workspace(self.conn, self.ws, TODAY)

    def cli(self, *argv) -> tuple:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = I.main(["--workspace", str(self.ws), "--memory", "--today", TODAY, *argv])
        return code, json.loads(buf.getvalue())


class TestIndex(Workspace):
    def test_schema_version_29_adds_the_table(self):
        self.assertEqual(I.SCHEMA_VERSION, 29)
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(gear_inspection)")}
        self.assertTrue({"gear_id", "condition", "distance_m", "wear_zones", "asymmetry_level",
                         "asymmetry_side", "photos", "previous"} <= cols, cols)

    def test_gear_folder_is_scanned_and_classified(self):
        self.assertIn("gear", I.DATA_DIRS)
        self.assertEqual(I.classify("gear/2026-09-20_pegasus_inspection.md"), "gear_inspection")
        self.assertIsNone(I.classify("gear/notes.md"))
        self.assertIsNone(I.classify("gear/2026-09-20_pegasus_semelles.md"))

    def test_inspection_is_indexed_with_json_columns(self):
        self.inspection("2026-09-20", distance_m=210000,
                        wear_zones=[{"side": "left", "zone": "heel_posterolateral", "severity": "moderate"},
                                    {"side": "right", "zone": "heel_posterolateral"}],
                        asymmetry={"level": "mild", "side": "left"}, gait_hints=["heel_strike"],
                        photos=[PHOTO], scale_reference=True, lug_depth_mm=2.5)
        self.index()
        rows = I._inspection_rows(self.conn)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["gear_id"], row["condition"], row["distance_m"], row["date"]),
                         ("pegasus", "yellow", 210000, "2026-09-20"))
        self.assertEqual(row["asymmetry"], {"level": "mild", "side": "left"})
        self.assertEqual(row["gait_hints"], ["heel_strike"])
        self.assertEqual(row["photos"], [PHOTO])
        self.assertTrue(row["scale_reference"])
        self.assertEqual(row["path"], "gear/2026-09-20_pegasus_inspection.md")

    def test_invalid_block_is_never_stored(self):
        self.inspection("2026-09-20", condition="amber")
        self.index()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gear_inspection").fetchone()[0], 0)
        status = self.conn.execute("SELECT parsed_ok FROM source_file WHERE path LIKE 'gear/%'").fetchone()[0]
        self.assertEqual(status, "invalid")

    def test_reindex_after_edit_and_removal(self):
        self.inspection("2026-09-20")
        self.index()
        self.inspection("2026-09-20", condition="red")
        self.index()
        self.assertEqual([r["condition"] for r in I._inspection_rows(self.conn)], ["red"])
        (self.ws / "gear/2026-09-20_pegasus_inspection.md").unlink()
        self.index()
        self.assertEqual(I._inspection_rows(self.conn), [])

    def test_validate_cli_and_filename_consistency(self):
        self.inspection("2026-09-20", distance_m=1000)
        ok, errors, warnings = I.validate_file(self.ws / "gear/2026-09-20_pegasus_inspection.md")
        self.assertEqual((ok, errors, warnings), (True, [], []))
        self.write("gear/2026-09-21_pegasus_inspection.md", arc_md(block(date="2026-09-20", gear_id="autre")))
        ok, errors, warnings = I.validate_file(self.ws / "gear/2026-09-21_pegasus_inspection.md")
        self.assertTrue(ok)
        self.assertEqual(len(warnings), 2, warnings)


class TestReminder(Workspace):
    def entry(self, gear_id="pegasus") -> dict:
        self.index()
        out = I.gear_inspections(self.conn, None, __import__("datetime").date.fromisoformat(TODAY))
        return next(e for e in out["gear"] if e["gear_id"] == gear_id)

    def test_never_inspected_is_due_from_200_km(self):
        self.profile("- Nike Pegasus — id: pegasus (par défaut)")
        self.activity("2026-09-01", 150000)
        e = self.entry()
        self.assertFalse(e["due"])
        self.activity("2026-09-10", 60000)
        e = self.entry()
        self.assertEqual((e["due"], e["due_reason"]), (True, "never_inspected"))
        self.assertEqual(e["km_since_inspection_m"], 210000)

    def test_interval_counts_from_last_inspection_distance(self):
        self.profile("- Nike Pegasus — id: pegasus (par défaut)")
        self.activity("2026-09-01", 300000)
        self.inspection("2026-09-02", distance_m=250000)
        e = self.entry()
        self.assertEqual((e["due"], e["km_since_inspection_m"]), (False, 50000))
        self.activity("2026-09-15", 160000)
        e = self.entry()
        self.assertEqual((e["due"], e["due_reason"]), (True, "interval"))

    def test_unknown_baseline_is_undetermined_not_guessed(self):
        self.profile("- Nike Pegasus — id: pegasus (par défaut)")
        self.activity("2026-09-01", 500000)
        self.inspection("2026-09-02")           # pas de distance_m
        e = self.entry()
        self.assertIsNone(e["due"])
        self.assertEqual(e["due_reason"], "baseline_unknown")

    def test_threshold_alert_without_inspection_beyond_threshold(self):
        self.profile("- Nike Pegasus — alerte 100 km — id: pegasus (par défaut)")
        self.activity("2026-09-01", 120000)
        self.inspection("2026-09-02", distance_m=90000)
        e = self.entry()
        self.assertEqual((e["due"], e["due_reason"]), (True, "threshold_alert"))
        self.inspection("2026-09-20", distance_m=118000)
        e = self.entry()
        self.assertFalse(e["due"])            # inspecté au-delà du seuil

    def test_retired_pair_is_never_due_but_keeps_history(self):
        self.profile("- Nike Pegasus — id: pegasus (retirée)")
        self.activity("2026-09-01", 900000, gear_id="pegasus")
        self.inspection("2026-09-02", distance_m=100000)
        e = self.entry()
        self.assertFalse(e["due"])
        self.assertEqual(len(e["inspections"]), 1)

    def test_retired_without_inspection_is_not_listed(self):
        self.profile("- Nike Pegasus — id: pegasus (retirée)\n- Hoka — id: hoka")
        self.index()
        ids = [e["gear_id"] for e in I.gear_inspections(self.conn)["gear"]]
        self.assertEqual(ids, ["hoka"])

    def test_condition_change_between_the_last_two(self):
        self.profile("- Nike Pegasus — id: pegasus (par défaut)")
        self.inspection("2026-08-01", condition="green")
        self.inspection("2026-09-01", condition="orange")
        self.assertEqual(self.entry()["condition_change"], "worse")
        self.inspection("2026-09-10", condition="green")
        self.assertEqual(self.entry()["condition_change"], "better")
        self.inspection("2026-09-15", condition="green")
        self.assertEqual(self.entry()["condition_change"], "same")

    def test_single_inspection_has_no_change(self):
        self.profile("- Nike Pegasus — id: pegasus (par défaut)")
        self.inspection("2026-09-01")
        self.assertNotIn("condition_change", self.entry())

    def test_inspection_of_a_pair_absent_from_the_profile_is_flagged_unknown(self):
        self.profile("- Hoka — id: hoka")
        self.inspection("2026-09-01", gear_id="fantome")
        e = self.entry("fantome")
        self.assertTrue(e["unknown"])
        self.assertFalse(e["due"])

    def test_history_is_newest_first(self):
        self.profile("- Nike Pegasus — id: pegasus (par défaut)")
        self.inspection("2026-08-01")
        self.inspection("2026-09-01")
        self.assertEqual([r["date"] for r in self.entry()["inspections"]], ["2026-09-01", "2026-08-01"])

    def test_cli_inspections_and_gear_filter(self):
        self.profile("- Nike Pegasus — id: pegasus (par défaut)\n- Hoka — id: hoka")
        self.inspection("2026-09-01")
        code, out = self.cli("inspections")
        self.assertEqual(code, 0)
        self.assertEqual(out["interval_m"], 200000)
        self.assertEqual({e["gear_id"] for e in out["gear"]}, {"pegasus", "hoka"})
        code, out = self.cli("inspections", "--gear", "pegasus")
        self.assertEqual([e["gear_id"] for e in out["gear"]], ["pegasus"])
        self.assertEqual(out["gear"][0]["latest"]["condition"], "yellow")

    def test_assumption_documents_the_method(self):
        self.assertIn("gear_inspection", M.ASSUMPTIONS)
        self.assertIn("200 km", M.ASSUMPTIONS["gear_inspection"])
        self.assertIn("approximation du projet", M.ASSUMPTIONS["gear_inspection"])


class TestCareer(Workspace):
    def setUp(self):
        super().setUp()
        self.profile("- Nike Pegasus — id: pegasus (retirée)\n- Hoka — id: hoka (par défaut)")

    def race_week(self, day: str) -> None:
        monday = __import__("datetime").date.fromisoformat(day)
        monday = monday - __import__("datetime").timedelta(days=monday.weekday())
        self.write(f"planning/Semaine_{monday.isoformat()}.md", arc_md({
            "arc": 1, "kind": "week", "week_start": monday.isoformat(), "location": "Tournai",
            "sessions": [{"date": day, "sport": "trail", "title": "Course", "intensity": "race"}]}))

    def test_career_summary(self):
        self.activity("2026-07-01", 12000, gear_id="pegasus", splits=True)
        self.activity("2026-08-01", 25000, gear_id="pegasus")
        self.activity("2026-08-02", 8000, gear_id="hoka")
        self.race_week("2026-08-01")
        self.inspection("2026-07-15", condition="green", distance_m=12000)
        self.inspection("2026-08-05", condition="orange", distance_m=37000)
        self.index()
        career = I.gear_career(self.conn, "pegasus", __import__("datetime").date.fromisoformat(TODAY))
        self.assertEqual(career["sessions"], 2)
        self.assertEqual(career["distance_m"], 37000)
        self.assertEqual((career["first_date"], career["last_date"]), ("2026-07-01", "2026-08-01"))
        self.assertEqual([r["date"] for r in career["races"]], ["2026-08-01"])
        self.assertEqual(career["longest"]["distance_m"], 25000)
        self.assertEqual(career["last_inspection"]["condition"], "orange")
        self.assertEqual([h["condition"] for h in career["condition_history"]], ["green", "orange"])
        self.assertEqual(career["inspections_count"], 2)
        self.assertTrue(career["retired"])
        # Records : seulement sur la séance à splits, jamais inventés.
        self.assertIn("best_efforts", career)
        self.assertEqual(career["best_efforts"][0]["km"], 1)

    def test_no_splits_no_best_efforts_key(self):
        self.activity("2026-08-01", 25000, gear_id="pegasus")
        self.index()
        career = I.gear_career(self.conn, "pegasus", __import__("datetime").date.fromisoformat(TODAY))
        self.assertNotIn("best_efforts", career)
        self.assertEqual(career["races"], [])
        self.assertNotIn("last_inspection", career)

    def test_default_pair_gets_unlabelled_sessions(self):
        self.activity("2026-08-01", 10000)          # pas de gear_id -> paire par défaut (hoka)
        self.index()
        career = I.gear_career(self.conn, "hoka", __import__("datetime").date.fromisoformat(TODAY))
        self.assertEqual(career["sessions"], 1)

    def test_start_mileage_is_counted_in_km_not_in_sessions(self):
        self.profile("- Nike Pegasus — id: pegasus (retirée) — départ 150 km")
        self.activity("2026-08-01", 25000, gear_id="pegasus")
        self.index()
        career = I.gear_career(self.conn, "pegasus", __import__("datetime").date.fromisoformat(TODAY))
        self.assertEqual((career["sessions"], career["distance_m"], career["counted_distance_m"],
                          career["start_m"]), (1, 175000, 25000, 150000))

    def test_unknown_pair_is_an_error(self):
        self.index()
        self.assertEqual(I.gear_career(self.conn, "nope"), {"error": "paire inconnue : nope"})

    def test_cli_gear_career(self):
        self.activity("2026-08-01", 25000, gear_id="pegasus")
        code, out = self.cli("gear-career", "--gear", "pegasus")
        self.assertEqual((code, out["sessions"]), (0, 1))
        code, out = self.cli("gear-career", "--gear", "nope")
        self.assertEqual(code, 1)
        self.assertIn("error", out)
        with self.assertRaises(I.ConfigError):
            self.cli("gear-career")


class TestPhotoRoute(Workspace):
    """`gear_photo_file` : seules les photos raster CITÉES par une inspection, sous gear/photos/."""

    def setUp(self):
        super().setUp()
        self.inspection("2026-09-20", photos=[PHOTO, "gear/photos/absente.jpg"])
        (self.ws / PHOTO).write_bytes(b"\xff\xd8\xff fake jpeg")
        self.store = S.Store(self.ws, memory=True, today=TODAY)

    def serve(self, rel):
        return S.gear_photo_file(self.store, rel)

    def test_cited_photo_is_served_with_a_raster_type(self):
        found = self.serve(PHOTO)
        self.assertIsNotNone(found)
        self.assertEqual((found[0].name, found[1]), ("2026-09-20_pegasus_semelles.jpg", "image/jpeg"))

    def test_missing_file_is_not_served(self):
        self.assertIsNone(self.serve("gear/photos/absente.jpg"))

    def test_uncited_file_is_not_served(self):
        (self.ws / "gear/photos/autre.jpg").write_bytes(b"x")
        self.assertIsNone(self.serve("gear/photos/autre.jpg"))

    def test_traversal_and_foreign_paths_are_refused(self):
        for rel in ("../ws/" + PHOTO, "gear/photos/../../planning/Runner_Profile.md", "/etc/passwd",
                    "planning/Runner_Profile.md", "gear/photos", None, "", "gear\\photos\\x.jpg"):
            self.assertIsNone(self.serve(rel), rel)

    def test_svg_and_html_are_never_served(self):
        for name in ("evil.svg", "evil.html", "evil.md"):
            (self.ws / "gear/photos" / name).write_text("<svg onload=alert(1)>", encoding="utf-8")
            self.inspection("2026-09-21", photos=[f"gear/photos/{name}"]) if name.endswith(".svg") else None
            self.assertIsNone(self.serve(f"gear/photos/{name}"), name)

    def test_symlink_escaping_the_photo_dir_is_refused(self):
        secret = self.tmp / "secret.jpg"
        secret.write_bytes(b"secret")
        link = self.ws / "gear/photos/lien.jpg"
        try:
            os.symlink(secret, link)
        except OSError:
            self.skipTest("liens symboliques indisponibles")
        self.inspection("2026-09-22", photos=["gear/photos/lien.jpg"])
        self.store = S.Store(self.ws, memory=True, today=TODAY)
        self.assertIsNone(self.serve("gear/photos/lien.jpg"))

    def test_oversize_file_is_refused(self):
        big = self.ws / "gear/photos/grosse.jpg"
        big.write_bytes(b"0")
        self.inspection("2026-09-22", photos=["gear/photos/grosse.jpg"])
        self.store = S.Store(self.ws, memory=True, today=TODAY)
        self.assertIsNotNone(self.serve("gear/photos/grosse.jpg"))
        original = S.GEAR_PHOTO_MAX_BYTES
        S.GEAR_PHOTO_MAX_BYTES = 0
        try:
            self.assertIsNone(self.serve("gear/photos/grosse.jpg"))
        finally:
            S.GEAR_PHOTO_MAX_BYTES = original


class TestSummary(Workspace):
    def test_summary_exposes_gear_inspections(self):
        self.profile("- Nike Pegasus — id: pegasus (par défaut)")
        self.inspection("2026-09-01", condition="green", distance_m=1000)
        store = S.Store(self.ws, memory=True, today=TODAY)
        summary = S.api_summary(store, {})
        gi = summary["gear_inspections"]
        self.assertEqual(gi["interval_m"], 200000)
        self.assertEqual(gi["gear"][0]["latest"]["condition"], "green")


if __name__ == "__main__":
    unittest.main()
