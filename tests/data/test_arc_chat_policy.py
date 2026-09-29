"""Palier D — politique de permissions du chat coach (`scripts/arc_chat_policy.py`)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import coach_config  # noqa: E402
from arc_chat_backend import payload_hash  # noqa: E402
from arc_chat_policy import Policy  # noqa: E402


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name).resolve()
        (self.ws / "planning").mkdir()
        self.policy = Policy.load(REPO, self.ws)

    def d(self, tool, tool_input=None, **kw):
        return self.policy.decide(tool, tool_input or {}, **kw)

    def test_fichier_versionne_charge(self):
        self.assertIn("planning", self.policy.write_dirs)
        self.assertIn("wttr.in", self.policy.fetch_domains)

    def test_lecture_dans_le_workspace(self):
        self.assertEqual(self.d("fs.read", {"path": "planning/active_objective.md"}), "allow")
        self.assertEqual(self.d("fs.list", {"path": "activities"}), "allow")
        self.assertEqual(self.d("fs.list", {}), "allow")

    def test_lecture_hors_workspace_ou_secrete_refusee(self):
        for path in ("../etc/passwd", "/etc/passwd", "config/workspace.user.toml", ".env",
                     "x/garmin.token", ".garminconnect/oauth.json", ".arc/chat/approvals.json"):
            self.assertEqual(self.d("fs.read", {"path": path}), "deny", path)

    def test_ecriture_limitee_aux_dossiers_de_donnees(self):
        for folder in ("activities", "medical", "nutrition", "planning", "rapports"):
            self.assertEqual(self.d("fs.write", {"path": f"{folder}/x.md"}), "allow", folder)
        for path in ("scripts/arc_chat.py", "config/workspace.toml", ".arc/chat/x.json", "AGENTS.md",
                     "planning/../scripts/x.py", "planning/.env"):
            self.assertEqual(self.d("fs.write", {"path": path}), "deny", path)

    def test_shell_liste_blanche_sans_metacaracteres(self):
        self.assertEqual(self.d("shell", {"command": "python3 scripts/arc_index.py energy"}), "allow")
        self.assertEqual(self.d("shell", {"command": "python3 scripts/arc_log.py --help"}), "allow")
        for command in ("rm -rf /", "python3 scripts/arc_index.py; rm x", "python3 scripts/arc_index.py | sh",
                        "python3 scripts/arc_index.py $(id)", "python3 scripts/arc_index.py > /tmp/x",
                        "python3 scripts/arc_index.py `id`", "python3 scripts/arc_index.py\nrm x",
                        "python3 scripts/arc_index.pyx", "python3 scripts/arc_index.py ../x", "", "python3 -c 1"):
            self.assertEqual(self.d("shell", {"command": command}), "deny", repr(command))

    def test_web(self):
        self.assertEqual(self.d("web.fetch", {"url": "https://wttr.in/Lyon?format=j1"}), "allow")
        self.assertEqual(self.d("web.fetch", {"url": "https://overpass-api.de/api/interpreter"}), "allow")
        self.assertEqual(self.d("web.fetch", {"url": "https://evil.example/wttr.in"}), "deny")
        self.assertEqual(self.d("web.fetch", {"url": "https://wttr.in.evil.example/"}), "deny")
        self.assertEqual(self.d("web.fetch", {"url": "https://user@evil.example@wttr.in/"}), "deny")
        self.assertEqual(self.d("web.fetch", {"url": "file:///etc/passwd"}), "deny")
        self.assertEqual(self.d("web.search", {"query": "x"}), "deny")

    def test_task_skill_autres(self):
        self.assertEqual(self.d("task", {"agent": "coach"}), "allow")
        self.assertEqual(self.d("skill", {"name": "log"}), "allow")
        self.assertEqual(self.d("other:WebSearch", {}), "deny")
        self.assertEqual(self.d("inconnu", {}), "deny")

    def test_mcp_lectures_autorisees(self):
        for tool in ("mcp:garmin.get_activities", "mcp:garmin.get_hrv_data", "mcp:garmin.count_activities",
                     "mcp:intervals.get_events", "mcp:garmin.download_workout"):
            self.assertEqual(self.d(tool), "allow", tool)

    def test_mcp_ecritures_demandent_approbation(self):
        names = ("schedule_workouts", "schedule_workout", "schedule_week", "delete_workout", "delete_workouts",
                 "unschedule_workout", "upload_workout", "upload_workouts", "upload_course", "delete_course",
                 "create_strength_workout", "create_z2_walk_workout", "add_weigh_in", "set_blood_pressure",
                 "log_food", "create_custom_food", "update_custom_food", "delete_food_log",
                 "add_or_update_event", "create_event", "bulk_create_events", "update_event", "delete_event",
                 "delete_events_by_date_range", "request_reload")
        for server in ("garmin", "intervals"):
            for name in names:
                self.assertEqual(self.d(f"mcp:{server}.{name}"), "ask", f"{server}.{name}")

    def test_mcp_outil_inconnu_ou_serveur_inconnu(self):
        self.assertEqual(self.d("mcp:garmin.upsert_and_log"), "ask")        # inconnu d'un serveur connu
        self.assertEqual(self.d("mcp:hassmcp.get_entity"), "deny")
        self.assertEqual(self.d("mcp:garmin."), "deny")

    def test_hash_preapprouve_leve_ask_seulement_pour_la_charge_exacte(self):
        tool, payload = "mcp:garmin.schedule_workouts", {"workouts": [{"date": "2026-10-01"}]}
        approved = {payload_hash(tool, payload)}
        self.assertEqual(self.d(tool, payload), "ask")
        self.assertEqual(self.d(tool, payload, preapproved=approved), "allow")
        self.assertEqual(self.d(tool, {"workouts": [{"date": "2026-10-02"}]}, preapproved=approved), "ask")
        # jamais une levée de « deny »
        denied = {payload_hash("shell", {"command": "rm -rf /"})}
        self.assertEqual(self.d("shell", {"command": "rm -rf /"}, preapproved=denied), "deny")

    def test_fichier_personnalise_et_repli_toml(self):
        custom = self.ws / "policy.toml"
        custom.write_text('[web]\nfetch_domains = ["example.org"]\n', encoding="utf-8")
        policy = Policy.load(custom, self.ws)
        self.assertEqual(policy.decide("web.fetch", {"url": "https://example.org/x"}), "allow")
        self.assertEqual(policy.decide("web.fetch", {"url": "https://wttr.in/"}), "deny")
        # Sans fichier : les défauts intégrés s'appliquent.
        empty = Policy.load(self.ws / "absent", self.ws)
        self.assertEqual(empty.decide("mcp:garmin.schedule_workouts", {}), "ask")

    def test_le_fichier_versionne_passe_le_parseur_de_repli(self):
        """Python < 3.11 : le repli de coach_config doit lire config/chat-policy.toml à l'identique."""
        text = (REPO / "config/chat-policy.toml").read_text(encoding="utf-8")
        parsed = coach_config._read_toml_fallback(text)
        try:
            import tomllib
        except ImportError:
            return
        real = tomllib.loads(text)
        for section in ("fs", "shell", "web", "mcp"):
            for key, value in real[section].items():
                self.assertEqual(parsed[section][key], value, f"{section}.{key}")


if __name__ == "__main__":
    unittest.main()
