"""Palier D — fiche d'une paire / d'un objet (#147) : `arc_index.gear_detail`,
`arc_index.gear_of_activity`, `arc_serve.api_gear` et `/api/activity/<id>.gear`.

Workspace minimal écrit à la main (même approche que `test_arc_serve_gear.py`). Verrouille surtout
que la fiche est bâtie sur la règle d'attribution UNIQUE : ses km et ses séances égalent ceux du
kilométrage (`/api/summary.gear`), jamais une seconde règle.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
import arc_metrics as M  # noqa: E402
import arc_serve as S  # noqa: E402
from tests.data.test_arc_serve_gear import GearApi, arc  # noqa: E402


class DetailCase(GearApi):
    def equipment_profile(self, shoes: str, equipment: str) -> None:
        self.write("planning/Runner_Profile.md",
                   f"# Profil\n\n## Matériel & lieux\n\n### Chaussures\n\n{shoes}\n\n### Matériel\n\n{equipment}\n")

    def worn(self, day: str, ids, sport: str = "trail", distance_m: float = 10000) -> None:
        self.write(f"activities/{day}_{sport}.md",
                   arc(json.dumps({"arc": 1, "kind": "activity", "date": day, "sport": sport, "duration_s": 3600,
                                   "distance_m": distance_m, "gear_ids": list(ids)})))

    def store(self):
        return S.Store(self.ws, memory=True, today=self.TODAY)


class TestShoeDetail(DetailCase):
    def test_sessions_and_km_match_the_mileage_rule(self):
        self.profile("- Hoka Speedgoat 5 — départ 100 km — alerte 200 km — id: speedgoat (par défaut)\n"
                     "- Nike Pegasus — id: pegasus")
        self.activity("2026-06-10", distance_m=10000)                       # défaut
        self.activity("2026-06-20", distance_m=12000, gear_id="pegasus")    # explicite
        self.activity("2026-09-10", distance_m=15000)                       # défaut, trois mois plus tard
        store = self.store()
        summary = S.api_summary(store, {})
        d = S.api_gear(store, "speedgoat")
        shoe = next(s for s in summary["gear"]["shoes"] if s["gear_id"] == "speedgoat")
        self.assertEqual(d["kind"], "shoe")
        self.assertEqual(d["career"]["distance_m"], shoe["distance_m"])
        self.assertEqual(d["career"]["sessions"], 2)
        self.assertEqual([s["date"] for s in d["sessions"]], ["2026-09-10", "2026-06-10"])   # récentes d'abord
        self.assertEqual(sum(s["distance_m"] for s in d["sessions"]) + 100000, shoe["distance_m"])
        peg = S.api_gear(store, "pegasus")
        self.assertEqual([s["date"] for s in peg["sessions"]], ["2026-06-20"])

    def test_monthly_km_is_continuous_and_excludes_start(self):
        self.profile("- Nike Pegasus — départ 100 km — id: pegasus (par défaut)")
        self.activity("2026-06-10", distance_m=10000)
        self.activity("2026-06-25", distance_m=5000)
        self.activity("2026-09-10", distance_m=15000)
        d = S.api_gear(self.store(), "pegasus")
        self.assertEqual(d["monthly"], [
            {"month": "2026-06", "distance_m": 15000}, {"month": "2026-07", "distance_m": 0},
            {"month": "2026-08", "distance_m": 0}, {"month": "2026-09", "distance_m": 15000}])

    def test_retired_shoe_is_still_available(self):
        self.profile("- Nike Pegasus — id: pegasus (retirée)")
        self.activity("2026-06-10", distance_m=10000, gear_id="pegasus")
        d = S.api_gear(self.store(), "pegasus")
        self.assertTrue(d["retired"])
        self.assertEqual(d["career"]["sessions"], 1)

    def test_unknown_id_seen_on_a_session_has_a_minimal_sheet(self):
        self.profile("- Nike Pegasus — id: pegasus")
        self.activity("2026-06-10", distance_m=9000, gear_id="jamais-vue")
        d = S.api_gear(self.store(), "jamais-vue")
        self.assertTrue(d["unknown"])
        self.assertEqual(d["career"]["distance_m"], 9000)
        self.assertEqual(len(d["sessions"]), 1)

    def test_ignored_shoe_has_no_mileage(self):
        self.profile("- Vieilles Trail — id: vieilles (ignorée)")
        d = S.api_gear(self.store(), "vieilles")
        self.assertTrue(d["ignored"])
        self.assertEqual(d["sessions"], [])

    def test_unknown_and_invalid_ids_are_none(self):
        self.profile("- Nike Pegasus — id: pegasus")
        store = self.store()
        for bad in ("absent", "", "..", "Pegasus", "a/b", "pegasus ", "x" * 200 + "!"):
            self.assertIsNone(S.api_gear(store, bad), bad)

    def test_inspection_entry_and_garmin_link(self):
        self.profile("- Nike Pegasus — id: pegasus — garmin: 0a1b2c3d-0000-4000-8000-000000000001")
        d = S.api_gear(self.store(), "pegasus")
        self.assertTrue(d["garmin_linked"])
        self.assertEqual(d["inspections"]["gear_id"], "pegasus")


class TestEquipmentDetail(DetailCase):
    def test_sessions_match_lifetime_usage_and_kits(self):
        self.equipment_profile(
            "- Nike Pegasus — id: pegasus (par défaut)",
            "- Bâtons Leki — catégorie: bâtons — alerte 500 km — id: batons — kit: trail-long\n"
            "- Frontale Petzl — catégorie: frontale — id: frontale — kit: trail-long")
        self.worn("2026-09-01", ["batons", "frontale"])
        self.worn("2026-09-05", ["batons"], distance_m=20000)
        self.worn("2026-09-07", ["batons"], sport="strength", distance_m=0)    # sport non compté : bâtons
        store = self.store()
        d = S.api_gear(store, "batons")
        self.assertEqual(d["kind"], "equipment")
        self.assertEqual(len(d["sessions"]), d["item"]["lifetime"]["sessions"])
        self.assertEqual([s["date"] for s in d["sessions"]], ["2026-09-05", "2026-09-01"])
        self.assertEqual([m["gear_id"] for m in d["kits"]["trail-long"]], ["batons", "frontale"])

    def test_unknown_equipment_id_from_gear_ids(self):
        self.equipment_profile("- Nike Pegasus — id: pegasus (par défaut)", "- Frontale — id: frontale")
        self.worn("2026-09-01", ["mystere"])
        d = S.api_gear(self.store(), "mystere")
        self.assertTrue(d["unknown"])
        self.assertEqual(d["unknown_usage"]["sessions"], 1)

    def test_session_counts_helper_mirrors_usage_filter(self):
        act = {"gear_ids": ["x"], "date": "2026-09-01", "sport": "strength"}
        self.assertFalse(M.equipment_session_counts(act, "x", "batons", "2026-09-23"))
        self.assertTrue(M.equipment_session_counts(act, "x", None, "2026-09-23"))
        self.assertFalse(M.equipment_session_counts(act, "x", None, "2026-08-01"))   # postérieure à today
        self.assertFalse(M.equipment_session_counts(act, "y", None, None))


class TestActivityGear(DetailCase):
    def test_activity_exposes_shoe_and_worn_equipment(self):
        self.equipment_profile("- Nike Pegasus — id: pegasus (par défaut)\n- Hoka Speedgoat — id: speedgoat",
                               "- Frontale — id: frontale")
        self.worn("2026-09-01", ["frontale", "mystere"])
        self.activity("2026-09-02", distance_m=10000, gear_id="speedgoat")
        store = self.store()
        by_date = {r["date"]: r["id"] for r in store.rows("SELECT id, date FROM activity")}
        default = S.api_activity(store, by_date["2026-09-01"])["gear"]
        self.assertEqual(default["shoe"]["gear_id"], "pegasus")
        self.assertEqual(default["shoe"]["source"], "default")
        self.assertEqual([(g["gear_id"], g["unknown"]) for g in default["equipment"]],
                         [("frontale", False), ("mystere", True)])
        explicit = S.api_activity(store, by_date["2026-09-02"])["gear"]
        self.assertEqual((explicit["shoe"]["gear_id"], explicit["shoe"]["source"]), ("speedgoat", "declared"))
        self.assertEqual(explicit["equipment"], [])

    def test_no_shoe_without_profile(self):
        self.activity("2026-09-02", distance_m=10000)
        store = self.store()
        aid = store.rows("SELECT id FROM activity")[0]["id"]
        self.assertEqual(S.api_activity(store, aid)["gear"], {"shoe": None, "equipment": []})


if __name__ == "__main__":
    unittest.main()
