"""Palier D — `scripts/garmin_gear_backfill.py` (#145) : planification pure (appariement, conflits,
ambiguïtés, arithmétique de « départ », filtres, repli de nom, collisions d'id), insertion de puces
dans le profil, réécriture textuelle du bloc `arc`, idempotence. Stdlib seule : client Garmin simulé
(`FakeClient`), workspace temporaire, aucun appel réseau, `garminconnect` non requis.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import arc_contract as C  # noqa: E402
import arc_index as I  # noqa: E402
import arc_legacy as L  # noqa: E402
import garmin_gear_backfill as B  # noqa: E402

U1 = "a1" * 16
U2 = "b2" * 16
U3 = "c3" * 16


def shoe(uuid=U1, name="Hoka Speedgoat 5", status="active", begin="2026-01-10T00:00:00.0", max_m=800000, typ="Shoes",
         custom=None):
    return {"uuid": uuid, "displayName": name, "customMakeModel": custom, "gearTypeName": typ,
            "gearStatusName": status, "dateBegin": begin, "maximumMeters": max_m}


def gact(aid, day, km=10.0):
    return {"activityId": aid, "startTimeLocal": f"{day} 07:00:00", "distance": km * 1000}


def ws(aid, day, km=10.0, gear_id=None, source=None, name=None):
    return {"path": f"activities/{day}_{name or aid}.md", "date": day, "garmin_activity_id": aid,
            "distance_m": km * 1000, "gear_id": gear_id, "gear_source": source, "has_block": True}


def acts(*items):
    return {"activities": B.normalize_gear_activities(list(items)), "error": None, "truncated": False}


def make_plan(raw_shoes, per_shoe, files, profile="", **kw):
    shoes = B.normalize_shoes(raw_shoes)
    gear_acts = {u: (v if isinstance(v, dict) else acts(*v)) for u, v in per_shoe.items()}
    return B.plan(shoes, gear_acts, files, L.parse_gear(profile), **kw)


class TestNormalize(unittest.TestCase):
    def test_only_shoes_and_name_fallbacks(self):
        raw = [shoe(U1, name=None, custom="Nike Pegasus"), shoe(U2, name=None, custom=None),
               shoe(U3, typ="Bike"), shoe("d4" * 16, name="  ")]
        out = B.normalize_shoes(raw)
        self.assertEqual([s["name"] for s in out],
                         ["Nike Pegasus", f"Chaussure Garmin {U2[:8]}", f"Chaussure Garmin {'d4' * 4}"])
        self.assertEqual(len(out), 3)

    def test_fields(self):
        s = B.normalize_shoes([shoe(status="retired", max_m=0)])[0]
        self.assertTrue(s["retired"])
        self.assertEqual(s["date_begin"], "2026-01-10")
        self.assertEqual(s["max_m"], 0.0)

    def test_gear_activities_dedup_and_date(self):
        out = B.normalize_gear_activities([gact(1, "2026-02-01"), gact(1, "2026-02-01"), {"activityId": "x"}])
        self.assertEqual(out, [{"id": 1, "date": "2026-02-01", "distance_m": 10000.0}])


class TestBullet(unittest.TestCase):
    def test_full_bullet_roundtrips_through_parser(self):
        s = B.normalize_shoes([shoe(status="retired")])[0]
        b = B.build_bullet(s, "hoka-speedgoat-5", 250)
        self.assertEqual(b, f"- Hoka Speedgoat 5 — depuis 2026-01-10 — alerte 800 km — départ 250 km — "
                            f"id: hoka-speedgoat-5 — garmin: {U1} (retirée)")
        g = L.parse_gear("### Chaussures\n\n" + b + "\n")[0]
        self.assertEqual((g["gear_id"], g["garmin_uuid"], g["start_m"], g["threshold_m"], g["retired"]),
                         ("hoka-speedgoat-5", U1, 250000, 800000, True))
        self.assertNotIn("default", g)

    def test_no_alert_when_max_is_zero_and_no_default_marker(self):
        s = B.normalize_shoes([shoe(max_m=0)])[0]
        b = B.build_bullet(s, "x", None)
        self.assertNotIn("alerte", b)
        self.assertNotIn("défaut", b)
        self.assertNotIn("départ", b)

    def test_hostile_names_are_sanitised(self):
        for name in ("Brooks — Ghost (retirée) 15", "Nike: depuis 2020", "Saucony - id: x", "A — départ 3 km"):
            s = B.normalize_shoes([shoe(name=name)])[0]
            bullet = B.build_bullet(s, "ok", None)
            g = L.parse_gear("### Chaussures\n" + bullet + "\n")[0]
            self.assertEqual(g["garmin_uuid"], U1, name)
            self.assertFalse(g.get("retired"), name)
            self.assertNotIn("start_m", g, name)

    def test_unique_ids_with_collisions(self):
        used = {"hoka-speedgoat-5", "hoka-speedgoat-5-2"}
        self.assertEqual(B.unique_gear_id("Hoka Speedgoat 5", U1, used), "hoka-speedgoat-5-3")
        self.assertEqual(B.unique_gear_id("Hoka Speedgoat 5", U1, used), "hoka-speedgoat-5-4")
        self.assertEqual(B.unique_gear_id("???", U2, set()), C.gear_slug(f"chaussure garmin {U2[:8]}"))


class TestPlanMatching(unittest.TestCase):
    def test_basic_matching_and_km(self):
        files = [ws(1, "2026-03-01"), ws(2, "2026-03-05", km=12), ws(3, "2026-03-09")]
        p = make_plan([shoe()], {U1: [gact(1, "2026-03-01"), gact(2, "2026-03-05", 12), gact(9, "2025-12-01", 20)]}, files)
        s = p["shoes"][0]
        self.assertEqual((s["status"], s["matched"], s["to_write"], s["workspace_km"], s["garmin_km"]),
                         ("new", 2, 2, 22.0, 42.0))
        self.assertEqual(len(p["assignments"]), 2)
        self.assertEqual(p["assignments"][0]["gear_id"], "hoka-speedgoat-5")
        self.assertEqual(p["workspace_without_id"], [])

    def test_workspace_files_without_id_counted(self):
        files = [ws(1, "2026-03-01"), ws(None, "2026-03-02")]
        p = make_plan([shoe()], {U1: [gact(1, "2026-03-01")]}, files)
        self.assertEqual(len(p["workspace_without_id"]), 1)
        self.assertEqual(p["workspace_with_id"], 1)

    def test_existing_athlete_declaration_is_kept_and_listed(self):
        files = [ws(1, "2026-03-01", gear_id="pegasus", source="chat"), ws(2, "2026-03-02")]
        p = make_plan([shoe()], {U1: [gact(1, "2026-03-01"), gact(2, "2026-03-02")]}, files)
        self.assertEqual(len(p["assignments"]), 1)
        self.assertEqual(p["assignments"][0]["path"], files[1]["path"])
        self.assertEqual(p["conflicts"][0]["kept"], "pegasus")
        self.assertEqual(p["conflicts"][0]["kept_source"], "chat")

    def test_same_gear_already_attributed_is_not_a_conflict(self):
        files = [ws(1, "2026-03-01", gear_id="hoka-speedgoat-5", source="garmin")]
        p = make_plan([shoe()], {U1: [gact(1, "2026-03-01")]}, files)
        self.assertEqual((p["shoes"][0]["already"], p["conflicts"], p["assignments"]), (1, [], []))

    def test_unmapped_is_replaced(self):
        files = [ws(1, "2026-03-01", source="garmin_unmapped")]
        p = make_plan([shoe()], {U1: [gact(1, "2026-03-01")]}, files)
        self.assertTrue(p["assignments"][0]["replaces_unmapped"])

    def test_ambiguous_activity_never_attributed(self):
        files = [ws(1, "2026-03-01"), ws(2, "2026-03-02")]
        p = make_plan([shoe(U1), shoe(U2, "Nike Pegasus")],
                      {U1: [gact(1, "2026-03-01"), gact(2, "2026-03-02")], U2: [gact(1, "2026-03-01")]}, files)
        self.assertEqual([a["path"] for a in p["assignments"]], [files[1]["path"]])
        self.assertEqual(p["ambiguous"][0]["id"], 1)
        self.assertEqual(sorted(p["ambiguous"][0]["shoes"]), sorted([U1, U2]))

    def test_ignored_bullet_skipped_and_existing_id_reused(self):
        profile = (f"### Chaussures\n\n- Vieille — id: vieille — garmin: {U2} (ignorée)\n"
                   f"- Ma Hoka — id: mes-hoka — garmin: {U1}\n")
        files = [ws(1, "2026-03-01"), ws(2, "2026-03-02")]
        p = make_plan([shoe(U1), shoe(U2, "Old")], {U1: [gact(1, "2026-03-01")], U2: [gact(2, "2026-03-02")]},
                      files, profile)
        by = {s["uuid"]: s for s in p["shoes"]}
        self.assertEqual(by[U1]["status"], "existing")
        self.assertEqual(p["assignments"][0]["gear_id"], "mes-hoka")
        self.assertEqual(by[U2]["status"], "ignored")
        self.assertEqual(len(p["assignments"]), 1)
        self.assertEqual(p["new_bullets"], [])

    def test_duplicate_uuid_in_profile_attributes_nothing(self):
        profile = f"### Chaussures\n- A — id: a — garmin: {U1}\n- B — id: b — garmin: {U1}\n"
        p = make_plan([shoe(U1)], {U1: [gact(1, "2026-03-01")]}, [ws(1, "2026-03-01")], profile)
        self.assertEqual(p["assignments"], [])
        self.assertEqual(p["shoes"][0]["status"], "duplicate_in_profile")

    def test_new_id_avoids_profile_and_equipment_collisions(self):
        profile = "### Chaussures\n- Hoka Speedgoat 5 — id: hoka-speedgoat-5\n"
        p = make_plan([shoe(U1)], {U1: [gact(1, "2026-03-01")]}, [ws(1, "2026-03-01")], profile,
                      extra_used_ids={"hoka-speedgoat-5-2"})
        self.assertEqual(p["shoes"][0]["gear_id"], "hoka-speedgoat-5-3")

    def test_two_new_shoes_same_name_get_distinct_ids(self):
        p = make_plan([shoe(U1), shoe(U2, begin="2026-02-01T00:00:00.0")],
                      {U1: [gact(1, "2026-03-01")], U2: [gact(2, "2026-03-02")]},
                      [ws(1, "2026-03-01"), ws(2, "2026-03-02")])
        self.assertEqual(sorted(s["gear_id"] for s in p["shoes"]), ["hoka-speedgoat-5", "hoka-speedgoat-5-2"])

    def test_gear_filter_and_since_filter(self):
        files = [ws(1, "2026-03-01"), ws(2, "2026-04-01")]
        per = {U1: [gact(1, "2026-03-01"), gact(2, "2026-04-01")], U2: [gact(3, "2026-04-02")]}
        p = make_plan([shoe(U1), shoe(U2, "Nike")], per, files, only_gear=U2.upper())
        self.assertEqual([s["uuid"] for s in p["shoes"]], [U2])
        p = make_plan([shoe(U1)], per, files, since="2026-03-15")
        self.assertEqual(len(p["assignments"]), 1)
        self.assertEqual(p["shoes"][0]["before_since"], 1)


class TestPeriodAndDepart(unittest.TestCase):
    def test_out_of_period_skipped_unless_all_shoes(self):
        old = shoe(U2, "Vieille", status="retired", begin="2022-01-01T00:00:00.0", max_m=0)
        per = {U1: [gact(1, "2026-03-01")], U2: [gact(50, "2023-01-01", 30), gact(51, "2023-02-01", 20)]}
        files = [ws(1, "2026-03-01")]
        p = make_plan([shoe(U1), old], per, files)
        self.assertEqual([b["uuid"] for b in p["new_bullets"]], [U1])
        p = make_plan([shoe(U1), old], per, files, all_shoes=True)
        bullet = next(b for b in p["new_bullets"] if b["uuid"] == U2)["bullet"]
        self.assertIn("(retirée)", bullet)
        self.assertIn("départ 50 km", bullet)
        self.assertEqual(p["assignments"][0]["gear_id"], "hoka-speedgoat-5")

    def test_depart_counts_only_garmin_sessions_absent_from_workspace(self):
        files = [ws(1, "2026-03-01", km=10), ws(2, "2026-03-05", km=12)]
        per = {U1: [gact(1, "2026-03-01", 10), gact(2, "2026-03-05", 12), gact(7, "2025-11-01", 40), gact(8, "2025-12-01", 60)]}
        s = make_plan([shoe()], per, files)["shoes"][0]
        self.assertEqual(s["depart_km"], 100)
        self.assertEqual(s["workspace_km"], 22.0)
        self.assertIn("100 km", s["depart_note"])
        self.assertIn("2 séance(s) Garmin", s["depart_note"])

    def test_workspace_km_plus_depart_equals_garmin_total(self):
        files = [ws(1, "2026-03-01", km=10)]
        per = {U1: [gact(1, "2026-03-01", 10), gact(7, "2025-11-01", 40)]}
        s = make_plan([shoe()], per, files)["shoes"][0]
        self.assertEqual(s["workspace_km"] + s["depart_km"], s["garmin_km"])

    def test_depart_skipped_with_since(self):
        s = make_plan([shoe()], {U1: [gact(1, "2026-03-01"), gact(7, "2025-11-01", 40)]},
                      [ws(1, "2026-03-01")], since="2026-01-01")["shoes"][0]
        self.assertIsNone(s["depart_km"])
        self.assertIn("--since", s["depart_note"])
        self.assertNotIn("départ", s["bullet"])

    def test_depart_skipped_when_truncated_or_id_less_file_same_day(self):
        per = {U1: {**acts(gact(1, "2026-03-01"), gact(7, "2025-11-01", 40)), "truncated": True}}
        s = make_plan([shoe()], per, [ws(1, "2026-03-01")])["shoes"][0]
        self.assertIsNone(s["depart_km"])
        self.assertIn("tronquée", s["depart_note"])
        files = [ws(1, "2026-03-05"), ws(None, "2026-03-06")]
        s = make_plan([shoe()], {U1: [gact(1, "2026-03-05"), gact(7, "2026-03-06", 40)]}, files)["shoes"][0]
        self.assertIsNone(s["depart_km"])
        self.assertIn("double comptage", s["depart_note"])

    def test_existing_bullet_never_gets_depart(self):
        profile = f"### Chaussures\n- Ma Hoka — id: mes-hoka — garmin: {U1}\n"
        p = make_plan([shoe()], {U1: [gact(1, "2026-03-01"), gact(7, "2025-11-01", 40)]}, [ws(1, "2026-03-01")], profile)
        self.assertIsNone(p["shoes"][0]["depart_km"])
        self.assertEqual(p["new_bullets"], [])

    def test_ambiguous_absent_session_excluded_from_depart(self):
        per = {U1: [gact(1, "2026-03-01"), gact(7, "2025-11-01", 40)], U2: [gact(7, "2025-11-01", 40)]}
        p = make_plan([shoe(U1), shoe(U2, "Nike")], per, [ws(1, "2026-03-01")])
        self.assertTrue(all(s["depart_km"] is None for s in p["shoes"]))

    def test_error_shoe_reported_not_proposed(self):
        per = {U1: {"activities": [], "error": "RuntimeError: 500", "truncated": False}}
        p = make_plan([shoe()], per, [ws(1, "2026-03-01")])
        self.assertEqual(p["shoes"][0]["status"], "error")
        self.assertEqual(p["new_bullets"], [])

    def test_idempotence_second_plan_is_empty(self):
        files = [ws(1, "2026-03-01"), ws(2, "2026-03-05")]
        per = {U1: [gact(1, "2026-03-01"), gact(2, "2026-03-05"), gact(7, "2025-11-01", 40)]}
        p1 = make_plan([shoe()], per, files)
        profile = B.insert_gear_bullets("# Profil\n", [b["bullet"] for b in p1["new_bullets"]])
        files2 = [ws(1, "2026-03-01", gear_id="hoka-speedgoat-5", source="garmin"),
                  ws(2, "2026-03-05", gear_id="hoka-speedgoat-5", source="garmin")]
        p2 = make_plan([shoe()], per, files2, profile)
        self.assertEqual((p2["assignments"], p2["new_bullets"], p2["conflicts"]), ([], [], []))
        self.assertEqual(p2["shoes"][0]["already"], 2)


class TestProfileInsertion(unittest.TestCase):
    B1 = f"- Hoka — id: hoka — garmin: {U1}"
    B2 = f"- Nike — id: nike — garmin: {U2}"

    def ids(self, text):
        return [g["gear_id"] for g in L.parse_gear(text)]

    def test_appends_after_last_bullet_without_touching_existing(self):
        text = ("## Matériel & lieux\n\n### Chaussures\n\n- Vieille — id: vieille (retirée)\n  - alerte 500 km\n\n"
                "Note.\n\n### Matériel\n- x\n")
        out = B.insert_gear_bullets(text, [self.B1, self.B2])
        self.assertIn("- Vieille — id: vieille (retirée)\n  - alerte 500 km\n" + self.B1 + "\n" + self.B2 + "\n\nNote.", out)
        self.assertEqual(self.ids(out), ["vieille", "hoka", "nike"])

    def test_empty_subsection_with_commented_template(self):
        text = "## Matériel & lieux\n\n### Chaussures\n\n<!-- exemple :\n- Fake — id: fake\n-->\n\n### Matériel\n"
        out = B.insert_gear_bullets(text, [self.B1])
        self.assertEqual(self.ids(out), ["hoka"])
        self.assertIn(self.B1 + "\n", out)
        self.assertIn("\n\n### Matériel", out)
        self.assertLess(out.index("-->"), out.index(self.B1))

    def test_commented_heading_is_not_the_section(self):
        text = "## Matériel & lieux\n\n<!--\n### Chaussures\n- Fake — id: fake\n-->\n\n### Matériel\n- Poche\n\n## Autre\n"
        out = B.insert_gear_bullets(text, [self.B1])
        self.assertEqual(self.ids(out), ["hoka"])
        self.assertLess(out.index("\n### Chaussures\n\n- Hoka"), out.index("### Matériel\n- Poche"))
        self.assertTrue(out.rstrip().endswith("## Autre"))

    def test_creates_subsection_at_end_of_section(self):
        text = "# Profil\n\n## Matériel & lieux\n\n- **Lieu par défaut** : Tournai\n\n## Objectifs\n\n- x\n"
        out = B.insert_gear_bullets(text, [self.B1])
        self.assertEqual(self.ids(out), ["hoka"])
        self.assertLess(out.index("### Chaussures"), out.index("## Objectifs"))
        self.assertGreater(out.index("### Chaussures"), out.index("Tournai"))
        self.assertIn("\n## Objectifs\n\n- x\n", out)

    def test_creates_section_when_absent(self):
        out = B.insert_gear_bullets("# Profil\n\n- **Nom** : Marco", [self.B1])
        self.assertEqual(self.ids(out), ["hoka"])
        self.assertIn("## Matériel & lieux\n\n### Chaussures", out)
        self.assertIn("- **Nom** : Marco\n", out)

    def test_existing_lines_preserved_verbatim(self):
        text = "## Matériel & lieux\n### Chaussures\n- A — id: a\n- B — id: b\n"
        out = B.insert_gear_bullets(text, [self.B1])
        self.assertTrue(out.startswith(text))


class TestSetBlockKeys(unittest.TestCase):
    def test_single_line_insertion_preserves_order_and_text(self):
        text = ('# T\n\n```arc\n{"arc": 1, "kind": "activity", "date": "2026-03-01", "sport": "trail", '
                '"duration_s": 60}\n```\n\nTexte.\n')
        out = B.set_block_keys(text, {"gear_id": "x", "gear_source": "garmin"})
        self.assertIn('"duration_s": 60, "gear_id": "x", "gear_source": "garmin"}\n```\n\nTexte.', out)
        self.assertEqual(C.extract_block(out)["gear_id"], "x")

    def test_multiline_insertion_keeps_indent(self):
        text = ('```arc\n{\n  "arc": 1, "kind": "activity", "date": "2026-03-01",\n'
                '  "sport": "trail", "duration_s": 60\n}\n```\n')
        out = B.set_block_keys(text, {"gear_id": "x", "gear_source": "garmin"})
        self.assertIn('"duration_s": 60,\n  "gear_id": "x",\n  "gear_source": "garmin"\n}', out)

    def test_replaces_unmapped_source(self):
        text = ('```arc\n{"arc": 1, "kind": "activity", "date": "2026-03-01", "sport": "trail", "duration_s": 60, '
                '"gear_source": "garmin_unmapped"}\n```\n')
        block = C.extract_block(B.set_block_keys(text, {"gear_id": "x", "gear_source": "garmin"}))
        self.assertEqual((block["gear_id"], block["gear_source"]), ("x", "garmin"))
        self.assertEqual(block["duration_s"], 60)


def write_activity(ws_dir: Path, name: str, **extra):
    block = {"arc": 1, "kind": "activity", "date": name[:10], "sport": "trail", "duration_s": 3600, **extra}
    (ws_dir / "activities").mkdir(exist_ok=True)
    (ws_dir / "activities" / name).write_text(
        f"# Séance\n\n```arc\n{json.dumps(block, ensure_ascii=False)}\n```\n\nTexte.\n", encoding="utf-8")


class TestApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        (self.ws / "planning").mkdir()
        self.profile = self.ws / "planning" / "Runner_Profile.md"
        self.profile.write_text("# Profil\n\n## Matériel & lieux\n\n- **Lieu par défaut** : Tournai\n", encoding="utf-8")
        write_activity(self.ws, "2026-03-01_trail.md", garmin_activity_id=1, distance_m=10000)
        write_activity(self.ws, "2026-03-05_trail.md", garmin_activity_id=2, distance_m=12000,
                       gear_id="pegasus", gear_source="chat")
        write_activity(self.ws, "2026-03-09_trail.md", distance_m=5000)
        self.addCleanup(self.tmp.cleanup)

    def run_plan(self):
        files = B.scan_workspace(self.ws)
        per = {U1: [gact(1, "2026-03-01"), gact(2, "2026-03-05", 12), gact(7, "2025-10-01", 40)]}
        return B.plan(B.normalize_shoes([shoe()]), {u: acts(*v) for u, v in per.items()}, files,
                      L.parse_gear(self.profile.read_text()))

    def snapshot(self):
        return {p: p.read_text() for p in [self.profile, *(self.ws / "activities").glob("*.md")]}

    def test_scan(self):
        files = B.scan_workspace(self.ws)
        self.assertEqual([f["garmin_activity_id"] for f in files], [1, 2, None])
        self.assertEqual(files[1]["gear_source"], "chat")

    def test_apply_writes_validates_and_is_idempotent(self):
        p = self.run_plan()
        self.assertEqual(len(p["assignments"]), 1)
        out = B.apply_plan(self.ws, self.profile, p)
        self.assertEqual((out["profile_written"], out["written"], out["failed"]),
                         (True, ["activities/2026-03-01_trail.md"], []))
        block = C.extract_block((self.ws / "activities/2026-03-01_trail.md").read_text())
        self.assertEqual((block["gear_id"], block["gear_source"]), ("hoka-speedgoat-5", "garmin"))
        chat = C.extract_block((self.ws / "activities/2026-03-05_trail.md").read_text())
        self.assertEqual(chat["gear_id"], "pegasus")   # jamais écrasée
        self.assertIn("départ 40 km", self.profile.read_text())
        self.assertIn("### Chaussures", self.profile.read_text())
        self.assertTrue(I.validate_file(self.ws / "activities/2026-03-01_trail.md")[0])
        before = self.snapshot()
        p2 = self.run_plan()
        self.assertEqual((p2["assignments"], p2["new_bullets"]), ([], []))
        out2 = B.apply_plan(self.ws, self.profile, p2)
        self.assertEqual(out2["written"], [])
        self.assertEqual(before, self.snapshot())

    def test_invalid_file_is_restored(self):
        p = self.run_plan()
        target = self.ws / "activities/2026-03-01_trail.md"
        original = target.read_text()
        out = B.apply_plan(self.ws, self.profile, p, validate=lambda _p: (False, ["refus simulé"], []))
        self.assertEqual(target.read_text(), original)
        self.assertEqual(out["failed"][0]["error"], "refus simulé")

    def test_planning_writes_nothing(self):
        before = self.snapshot()
        self.run_plan()
        self.assertEqual(before, self.snapshot())

    def test_gear_total_after_reindex_equals_garmin_total(self):
        p = self.run_plan()
        B.apply_plan(self.ws, self.profile, p)
        r = B.reindex(self.ws)
        row = next(g for g in r["gear"]["shoes"] if g["gear_id"] == "hoka-speedgoat-5")
        self.assertEqual(round(row["distance_m"]), 10000 + 40000)


class TestReport(unittest.TestCase):
    def test_report_is_french_and_mentions_sections(self):
        files = [ws(1, "2026-03-01", gear_id="autre", source="chat"), ws(None, "2026-03-02")]
        p = make_plan([shoe()], {U1: [gact(1, "2026-03-01"), gact(7, "2025-11-01", 40)]}, files)
        text = B.render_report(p)
        for needle in ("simulation", "puce proposée", "CONFLITS", "FICHIERS SANS garmin_activity_id", "--apply",
                       "SÉANCES GARMIN ABSENTES"):
            self.assertIn(needle, text)
        json.dumps(p)


if __name__ == "__main__":
    unittest.main()
