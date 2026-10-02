"""Palier D — scénario rejoué du backend `mock` (`[chat].mock_scenario`, vidéos et captures).

Aucun réseau, aucun modèle : un `TurnContext` factice collecte les événements. Les délais sont
neutralisés par `mock_scenario_speed`.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import arc_chat_mock as M  # noqa: E402
from arc_chat_backend import BackendError, TurnContext  # noqa: E402

VIDEO_SCENARIO = REPO / "docs/video/data/chat-scenario.fr.json"

SMALL = {
    "chunk_chars": 5, "chunk_delay_s": 0.5,
    "turns": [
        {"match": "bonjour", "steps": [
            {"text": "Salut coach !", "part": "r1"},
            {"tool": {"id": "a1", "name": "fs.read", "summary": "Lecture", "result": "ok", "delay_s": 1}},
            {"file_written": "planning/x.md"},
            {"marker": "stop"},
            {"approval": {"tool": "mcp:garmin.schedule_workouts", "input": {"w": 1}, "summary": "S",
                          "diff": [{"op": "+", "text": "x"}],
                          "allow": [{"text": "Fait."}], "deny": [{"text": "Non."}],
                          "pending": [{"text": "Attente."}]}},
        ]},
    ],
}


def run(backend, message, decision="allow", policy="ask"):
    events = []
    ctx = TurnContext(
        session_id="s1", workspace=Path("/nonexistent"), config={},
        emit=lambda kind, payload: events.append((kind, payload)),
        decide=lambda tool, tool_input: policy,
        request_approval=lambda tool, tool_input, summary, diff: decision,
    )
    backend.run_turn(ctx, message)
    return events, ctx


class ScenarioCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, data, name="s.json") -> str:
        path = self.dir / name
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return str(path)

    def backend(self, data=SMALL, **config):
        cfg = {"mock_scenario": self.write(data), "mock_scenario_speed": 1000, **config}
        return M.MockBackend(self.dir, cfg)


class TestLoader(ScenarioCase):
    def test_fichier_absent_message_clair(self):
        with self.assertRaises(BackendError) as cm:
            M.MockBackend(self.dir, {"mock_scenario": "nope.json"})
        self.assertIn("introuvable", str(cm.exception))
        self.assertIn("nope.json", str(cm.exception))

    def test_json_invalide(self):
        with self.assertRaises(BackendError) as cm:
            self.backend("{pas du json")
        self.assertIn("illisible", str(cm.exception))
        self.assertIn("s.json", str(cm.exception))

    def test_regex_invalide_nomme_le_tour(self):
        with self.assertRaises(BackendError) as cm:
            self.backend({"turns": [{"match": "(", "steps": [{"text": "x"}]}]})
        self.assertIn("turns[0].match", str(cm.exception))

    def test_etape_inconnue_ou_ambigue(self):
        with self.assertRaises(BackendError) as cm:
            self.backend({"turns": [{"match": "a", "steps": [{"danse": 1}]}]})
        self.assertIn("turns[0].steps[0]", str(cm.exception))
        with self.assertRaises(BackendError):
            self.backend({"turns": [{"match": "a", "steps": [{"text": "x", "pause_s": 1}]}]})

    def test_delai_negatif_et_diff_invalide(self):
        with self.assertRaises(BackendError):
            self.backend({"turns": [{"match": "a", "steps": [{"pause_s": -1}]}]})
        bad = {"turns": [{"match": "a", "steps": [{"approval": {
            "tool": "t", "input": {}, "summary": "s", "diff": [{"op": "?", "text": "x"}]}}]}]}
        with self.assertRaises(BackendError) as cm:
            self.backend(bad)
        self.assertIn("diff", str(cm.exception))

    def test_racine_sans_tours(self):
        with self.assertRaises(BackendError):
            self.backend({"turns": []})
        with self.assertRaises(BackendError):
            self.backend([1, 2])

    def test_vitesse_invalide(self):
        with self.assertRaises(BackendError) as cm:
            self.backend(mock_scenario_speed=0)
        self.assertIn("mock_scenario_speed", str(cm.exception))

    def test_sans_scenario_comportement_habituel(self):
        backend = M.MockBackend(self.dir, {})
        events, _ = run(backend, "Je suis fatigué")
        kinds = [k for k, _ in events]
        self.assertEqual(kinds[-1], "done")
        self.assertTrue(any(k == "file_written" and p["path"].endswith("readiness-basse.md") for k, p in events))

    def test_scenario_relatif_au_workspace(self):
        self.write(SMALL, "rel.json")
        backend = M.MockBackend(self.dir, {"mock_scenario": "rel.json"})
        self.assertIsNotNone(backend.scenario)


class TestReplay(ScenarioCase):
    def test_correspondance_regex_insensible_a_la_casse(self):
        backend = self.backend()
        events, _ = run(backend, "BONJOUR coach")
        self.assertTrue(any(k == "text_delta" and "Salut" in p["text"] for k, p in events))
        # pas de correspondance : le mock habituel répond (aucun texte du scénario)
        events, _ = run(backend, "autre chose")
        self.assertFalse(any("Salut" in p.get("text", "") for k, p in events if k == "text_delta"))

    def test_deterministe(self):
        backend = self.backend()
        first, _ = run(backend, "bonjour")
        second, _ = run(backend, "bonjour")
        self.assertEqual(first, second)

    def test_texte_decoupe_en_morceaux_et_parts(self):
        events, _ = run(self.backend(), "bonjour")
        deltas = [p for k, p in events if k == "text_delta"][:3]
        self.assertEqual([d["text"] for d in deltas], ["Salut", " coac", "h !"])
        self.assertTrue(all(d["part"] == "r1" for d in deltas))

    def test_trace_outil_et_fichier(self):
        events, _ = run(self.backend(), "bonjour")
        kinds = [k for k, _ in events]
        self.assertLess(kinds.index("tool_start"), kinds.index("tool_end"))
        self.assertIn(("file_written", {"path": "planning/x.md"}), events)
        self.assertEqual(kinds[-2:], ["usage", "done"])

    def test_approbation_allow_deny_pending(self):
        backend = self.backend()
        events, _ = run(backend, "bonjour", decision="allow")
        texts = "".join(p.get("text", "") for k, p in events if k == "text_delta")
        self.assertIn("Fait.", texts)
        self.assertEqual(events[-1], ("done", {"reason": "end_turn"}))
        events, _ = run(backend, "bonjour", decision="deny")
        self.assertIn("Non.", "".join(p.get("text", "") for k, p in events if k == "text_delta"))
        events, _ = run(backend, "bonjour", decision="pending")
        self.assertIn("Attente.", "".join(p.get("text", "") for k, p in events if k == "text_delta"))
        self.assertEqual(events[-1], ("done", {"reason": "pending_approval"}))

    def test_politique_deny_saute_l_approbation(self):
        events, _ = run(self.backend(), "bonjour", policy="deny")
        self.assertIn("Non.", "".join(p.get("text", "") for k, p in events if k == "text_delta"))

    def test_hold_suspend_au_marqueur_jusqu_a_l_interruption(self):
        backend = self.backend(mock_scenario_hold="stop")
        events = []
        ctx = TurnContext(session_id="s", workspace=Path("/x"), config={},
                          emit=lambda k, p: events.append((k, p)), decide=lambda t, i: "ask",
                          request_approval=lambda *a: "allow")
        worker = threading.Thread(target=backend.run_turn, args=(ctx, "bonjour"))
        worker.start()
        worker.join(0.5)
        self.assertTrue(worker.is_alive(), "le tour doit rester suspendu au marqueur")
        self.assertFalse(any(k == "approval_request" for k, _ in events))
        ctx.cancelled.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(events[-1], ("done", {"reason": "interrupted"}))

    def test_interruption_pendant_la_frappe(self):
        backend = M.MockBackend(self.dir, {"mock_scenario": self.write(SMALL), "mock_scenario_speed": 1})
        events = []
        ctx = TurnContext(session_id="s", workspace=Path("/x"), config={},
                          emit=lambda k, p: events.append((k, p)), decide=lambda t, i: "ask",
                          request_approval=lambda *a: "allow")
        ctx.cancelled.set()
        backend.run_turn(ctx, "bonjour")
        self.assertEqual(events[-1], ("done", {"reason": "interrupted"}))


class TestVideoScenario(ScenarioCase):
    """Le scénario livré pour les vidéos reste valide et suit l'histoire de Camille."""

    def setUp(self):
        super().setUp()
        self.backend_ = M.MockBackend(self.dir, {"mock_scenario": str(VIDEO_SCENARIO), "mock_scenario_speed": 1000})

    def text_of(self, events):
        return "".join(p.get("text", "") for k, p in events if k == "text_delta")

    def test_tour_seuil(self):
        events, _ = run(self.backend_, "Je me sens vidé·e ce matin, je fais quand même mon seuil ?")
        text = self.text_of(events)
        for needle in ("38 ms", "52 bpm", "34/100", "EF 45"):
            self.assertIn(needle, text)
        self.assertIn(("file_written", {"path": "planning/2026-09-29_decision_bilan-matinal.md"}), events)
        self.assertEqual(events[-1], ("done", {"reason": "end_turn"}))

    def test_tour_samedi(self):
        events, _ = run(self.backend_, "Et pour samedi ?")
        text = self.text_of(events)
        self.assertIn("sortie longue", text)
        self.assertIn("tôt le matin", text)


if __name__ == "__main__":
    unittest.main()
