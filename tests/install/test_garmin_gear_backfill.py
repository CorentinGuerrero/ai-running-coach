"""Palier A — `scripts/garmin_gear_backfill.py` (#145) de bout en bout : CLI lancée dans le bac à sable sur un
workspace temporaire, avec un client Garmin SIMULÉ (`--fake-client`, aucun réseau, aucun jeton, aucun
`garminconnect`). Vérifie : la simulation n'écrit rien, `--apply` écrit/valide/réindexe, la seconde exécution
ne change rien, les totaux `arc_index.py gear`, les codes de sortie et la sortie `--json`.
"""

from __future__ import annotations

import json
import subprocess
import sys

from tests.lib.asserts import InstallAsserts
from tests.lib.sandbox import Sandbox

U1 = "a1" * 16
U2 = "b2" * 16
U3 = "c3" * 16

FIXTURE = {
    "profile_id": 42,
    "gear": [
        {"uuid": U1, "displayName": "Hoka Speedgoat 5", "customMakeModel": None, "gearTypeName": "Shoes",
         "gearStatusName": "active", "dateBegin": "2026-01-10T00:00:00.0", "maximumMeters": 800000},
        {"uuid": U2, "displayName": None, "customMakeModel": "Nike Pegasus", "gearTypeName": "Shoes",
         "gearStatusName": "retired", "dateBegin": "2022-05-01T00:00:00.0", "maximumMeters": 0},
        {"uuid": U3, "displayName": "Gravel", "gearTypeName": "Bike", "gearStatusName": "active"},
    ],
    "defaults": [{"uuid": U1, "activityTypePk": 1}],
    "gear_activities": {
        U1: [
            {"activityId": 1001, "startTimeLocal": "2026-03-01 07:00:00", "distance": 10000},
            {"activityId": 1002, "startTimeLocal": "2026-03-05 07:00:00", "distance": 12000},
            {"activityId": 1003, "startTimeLocal": "2026-03-09 07:00:00", "distance": 8000},
            {"activityId": 900, "startTimeLocal": "2025-12-01 07:00:00", "distance": 40000},
        ],
        U2: [
            {"activityId": 800, "startTimeLocal": "2023-01-01 07:00:00", "distance": 30000},
            {"activityId": 801, "startTimeLocal": "2023-02-01 07:00:00", "distance": 20000},
        ],
    },
}

PROFILE = "# Profil\n\n## Matériel & lieux\n\n- **Lieu par défaut** : Tournai\n"


def _activity(sb, name, **extra):
    block = {"arc": 1, "kind": "activity", "date": name[:10], "sport": "trail", "duration_s": 3600, **extra}
    path = sb.repo / "activities" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(f"# Séance\n\n```arc\n{json.dumps(block)}\n```\n\nTexte.\n", encoding="utf-8")
    return path


def _setup(sb, fixture=FIXTURE):
    (sb.repo / "planning").mkdir(exist_ok=True)
    (sb.repo / "planning" / "Runner_Profile.md").write_text(PROFILE, encoding="utf-8")
    _activity(sb, "2026-03-01_trail.md", garmin_activity_id=1001, distance_m=10000)
    _activity(sb, "2026-03-05_trail.md", garmin_activity_id=1002, distance_m=12000, gear_id="pegasus", gear_source="chat")
    _activity(sb, "2026-03-09_trail.md", garmin_activity_id=1003, distance_m=8000)
    _activity(sb, "2026-03-12_trail.md", distance_m=5000)
    fake = sb.root / "fake-garmin.json"
    fake.write_text(json.dumps(fixture), encoding="utf-8")
    return fake


class TestGearBackfillCli(InstallAsserts):
    def _run(self, sb, fake, *args):
        return sb.script("garmin_gear_backfill.py", "--workspace", str(sb.repo), "--fake-client", str(fake), *args)

    def _tree(self, sb):
        return {str(p): p.read_bytes() for p in sb.repo.rglob("*") if p.is_file()
                and ".arc" not in p.parts and ".git" not in p.parts}

    def test_dry_run_writes_nothing_and_reports(self):
        with Sandbox() as sb:
            fake = _setup(sb)
            before = self._tree(sb)
            proc = self._run(sb, fake)
            self.assertSucceeded(proc)
            self.assertEqual(before, self._tree(sb))
            out = proc.stdout
            self.assertIn("simulation", out)
            self.assertIn("Hoka Speedgoat 5", out)
            self.assertIn("puce proposée", out)
            self.assertIn("CONFLITS", out)          # 1002 porte déjà « pegasus » (chat)
            self.assertIn("FICHIERS SANS garmin_activity_id : 1", out)
            self.assertIn("PAIRES PAR DÉFAUT CHEZ GARMIN", out)
            self.assertNotIn("Nike Pegasus", out.split("PAIRES")[1].split("CONFLITS")[0])  # paire hors période masquée

    def test_json_output_is_machine_readable(self):
        with Sandbox() as sb:
            fake = _setup(sb)
            proc = self._run(sb, fake, "--json")
            self.assertSucceeded(proc)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["dry_run"])
            self.assertEqual(len(payload["assignments"]), 2)
            self.assertEqual(len(payload["new_bullets"]), 1)
            self.assertIn("départ 40 km", payload["new_bullets"][0]["bullet"])
            self.assertNotIn("applied", payload)

    def test_apply_then_idempotent_and_totals(self):
        with Sandbox() as sb:
            fake = _setup(sb)
            proc = self._run(sb, fake, "--apply", "--json")
            self.assertSucceeded(proc)
            payload = json.loads(proc.stdout)
            self.assertEqual(sorted(payload["applied"]["written"]),
                             ["activities/2026-03-01_trail.md", "activities/2026-03-09_trail.md"])
            self.assertEqual(payload["applied"]["failed"], [])
            profile = (sb.repo / "planning/Runner_Profile.md").read_text(encoding="utf-8")
            self.assertIn("### Chaussures", profile)
            self.assertIn(f"garmin: {U1}", profile)
            self.assertNotIn("par défaut)", profile.split("### Chaussures")[1])
            chat = (sb.repo / "activities/2026-03-05_trail.md").read_text(encoding="utf-8")
            self.assertIn('"gear_id": "pegasus"', chat)
            # totaux : 10 + 8 km attribués + 12 km « pegasus » ; départ 40 km sur la Hoka -> 58 km
            gear = subprocess.run(
                [sys.executable, str(sb.repo / "scripts/arc_index.py"), "gear", "--workspace", str(sb.repo)],
                capture_output=True, text=True, env=sb.env())
            rows = {g["gear_id"]: g for g in json.loads(gear.stdout)["shoes"]}
            self.assertEqual(round(rows["hoka-speedgoat-5"]["distance_m"]), 58000)
            valid = subprocess.run(
                [sys.executable, str(sb.repo / "scripts/arc_index.py"), "--validate",
                 str(sb.repo / "activities/2026-03-01_trail.md")], capture_output=True, text=True, env=sb.env())
            self.assertEqual(valid.returncode, 0, valid.stdout)
            before = self._tree(sb)
            again = self._run(sb, fake, "--apply", "--json")
            self.assertSucceeded(again)
            second = json.loads(again.stdout)
            self.assertEqual((second["assignments"], second["new_bullets"], second["applied"]["written"]), ([], [], []))
            self.assertEqual(before, self._tree(sb))

    def test_gear_and_since_filters(self):
        with Sandbox() as sb:
            fake = _setup(sb)
            payload = json.loads(self._run(sb, fake, "--json", "--since", "2026-03-08").stdout)
            self.assertEqual([a["path"] for a in payload["assignments"]], ["activities/2026-03-09_trail.md"])
            self.assertNotIn("départ", payload["new_bullets"][0]["bullet"])
            payload = json.loads(self._run(sb, fake, "--json", "--all-shoes", "--gear", U2).stdout)
            self.assertEqual([s["uuid"] for s in payload["shoes"]], [U2])
            self.assertIn("(retirée)", payload["new_bullets"][0]["bullet"])

    def test_exit_codes(self):
        with Sandbox() as sb:
            fake = _setup(sb)
            self.assertEqual(self._run(sb, fake, "--since", "pas-une-date").returncode, 2)
            self.assertEqual(self._run(sb, fake, "--gear", "f" * 32).returncode, 2)
            (sb.repo / "planning/Runner_Profile.md").unlink()
            self.assertEqual(self._run(sb, fake, "--apply").returncode, 3)
            self.assertEqual(self._run(sb, fake).returncode, 0)   # simulation sans profil : possible
            broken = dict(FIXTURE, gear_activities={**FIXTURE["gear_activities"], U1: "HTTP 500"})
            fake2 = _setup(sb, broken)
            proc = self._run(sb, fake2)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("erreur Garmin", proc.stdout)

    # -- revue #145 ----------------------------------------------------------------------------------
    def test_gear_filter_keeps_ambiguity_detection(self):
        with Sandbox() as sb:
            spec = json.loads(json.dumps(FIXTURE))
            spec["gear_activities"][U2].append(
                {"activityId": 1001, "startTimeLocal": "2026-03-01 07:00:00", "distance": 10000})
            fake = _setup(sb, spec)
            payload = json.loads(self._run(sb, fake, "--json", "--gear", U1, "--apply").stdout)
            self.assertEqual([a["id"] for a in payload["ambiguous"]], [1001])
            self.assertEqual(payload["applied"]["written"], ["activities/2026-03-09_trail.md"])
            self.assertNotIn('"gear_id"', (sb.repo / "activities/2026-03-01_trail.md").read_text(encoding="utf-8"))

    def test_apply_refused_and_nothing_written_when_a_pair_errors(self):
        with Sandbox() as sb:
            broken = dict(FIXTURE, gear_activities={**FIXTURE["gear_activities"], U2: "HTTP 500"})
            fake = _setup(sb, broken)
            before = self._tree(sb)
            proc = self._run(sb, fake, "--apply", "--gear", U1)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("--apply REFUSÉ", proc.stdout)
            self.assertEqual(before, self._tree(sb))
            self.assertFalse((sb.repo / ".arc").exists())

    def test_duplicate_files_reported_and_not_written(self):
        with Sandbox() as sb:
            fake = _setup(sb)
            _activity(sb, "2026-03-01_trail_2.md", garmin_activity_id=1001, distance_m=10000)
            payload = json.loads(self._run(sb, fake, "--json", "--apply").stdout)
            self.assertEqual(payload["duplicate_ids"][0]["id"], 1001)
            self.assertNotIn("activities/2026-03-01_trail.md", payload["applied"]["written"])
            self.assertNotIn('"gear_id"', (sb.repo / "activities/2026-03-01_trail_2.md").read_text(encoding="utf-8"))
