"""Palier A — seconde revue du service de chat : budget, reprises, approbations, limiteur.

Même bac à sable que `test_chat_review_fixes.py` (serveur réel, backend scripté).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import arc_chat as C  # noqa: E402
from arc_chat_mock import TOOL_INPUT as MOCK_INPUT  # noqa: E402
from arc_chat_mock import TOOL as MOCK_TOOL  # noqa: E402
from tests.data.test_arc_chat_claude import MB, make_fake_sdk  # noqa: E402
from tests.install.test_chat_review_fixes import propose_then_pending, scripted  # noqa: E402
from tests.install.test_chat_service import CSRF, ChatCase, wait_for  # noqa: E402


def resume_executes(ctx, message):
    """Reprise : exécute l'appel pré-approuvé ; sinon (premier tour) ne fait rien."""
    if message.startswith("[approbation]") and ctx.decide(MOCK_TOOL, MOCK_INPUT) == "allow":
        ctx.emit("tool_start", {"id": "t2", "name": MOCK_TOOL, "summary": "Planification"})
    ctx.emit("done", {"reason": "end_turn"})


def tool_runs(log):
    return sum(1 for e in log if e["type"] == "tool_start" and e["data"]["name"] == MOCK_TOOL)


class TestRound2(ChatCase):
    def session_log(self, sid):
        return self.get(f"/api/chat/sessions/{sid}")[2]["events"]

    def approvals_file(self):
        return self.ws / ".arc/chat/approvals.json"

    def record(self, aid):
        return json.loads(self.approvals_file().read_text(encoding="utf-8"))[aid]

    # -- B3 : plafond Claude de bout en bout ------------------------------------------------

    def test_b3_plafond_du_tour_claude_vient_du_budget_restant_du_service(self):
        record: dict = {}
        saved = sys.modules.get("claude_agent_sdk")
        sys.modules["claude_agent_sdk"] = make_fake_sdk([("msg", MB.ResultMessage())], record)
        old_key = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = "sk-test"

        def restore():
            if saved is None:
                sys.modules.pop("claude_agent_sdk", None)
            else:
                sys.modules["claude_agent_sdk"] = saved
            if old_key is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = old_key

        self.addCleanup(restore)
        from arc_chat_claude import ClaudeBackend
        service = self.start(daily_budget_eur=2.0, usd_eur_rate=0.92, backend="claude",
                             backend_factory=ClaudeBackend)
        service.spend.add(0.5)
        _, _, events = self.stream(self.new_session(), "salut")
        self.assertEqual(events[-1][0], "done")
        self.assertAlmostEqual(record["options"].max_budget_usd, round(1.5 / 0.92, 6), places=5)

    # -- S2 : reprises au démarrage -----------------------------------------------------------

    def queue_resume(self, aid, **fields):
        data = json.loads(self.approvals_file().read_text(encoding="utf-8"))
        data[aid].update(status="allowed", **fields)
        self.approvals_file().write_text(json.dumps(data), encoding="utf-8")

    def pending_approval(self):
        self.start(approval_wait_s=0.2, backend_factory=scripted(propose_then_pending))
        sid = self.new_session()
        _, _, events = self.stream(sid, "planifie")
        return sid, next(d["approval_id"] for t, d in events if t == "approval_request")

    def test_s2_reprise_deja_demarree_n_est_jamais_rejouee(self):
        sid, aid = self.pending_approval()
        self.queue_resume(aid, resume="running", resolved_ts=time.time())
        self.start(backend_factory=scripted(resume_executes))          # redémarrage du service
        self.assertTrue(wait_for(lambda: self.get(f"/api/chat/approvals/{aid}")[2]["status"] == "unexecuted"))
        time.sleep(0.2)
        self.assertEqual(tool_runs(self.session_log(sid)), 0)
        self.assertIn("error", [e["type"] for e in self.session_log(sid)])

    def test_s2_reprise_en_file_expiree_n_est_pas_rejouee(self):
        sid, aid = self.pending_approval()
        self.queue_resume(aid, resume="queued", resolved_ts=time.time() - 90000)   # > approval_ttl_s (86400)
        self.start(backend_factory=scripted(resume_executes))
        self.assertTrue(wait_for(lambda: self.get(f"/api/chat/approvals/{aid}")[2]["status"] == "unexecuted"))
        self.assertEqual(tool_runs(self.session_log(sid)), 0)

    def test_s2_reprise_recente_en_file_est_rejouee(self):
        sid, aid = self.pending_approval()
        self.queue_resume(aid, resume="queued", resolved_ts=time.time() - 60)
        self.start(backend_factory=scripted(resume_executes))
        self.assertTrue(wait_for(lambda: tool_runs(self.session_log(sid)) == 1))

    def test_s2_reprise_marquee_running_des_le_debut_du_tour(self):
        seen = []

        def behaviour(ctx, message):
            if message.startswith("[approbation]"):
                data = json.loads(self.approvals_file().read_text(encoding="utf-8"))
                seen.extend(rec.get("resume") for rec in data.values())
            propose_then_pending(ctx, message)

        self.start(approval_wait_s=0.2, backend_factory=scripted(behaviour))
        sid = self.new_session()
        _, _, events = self.stream(sid, "planifie")
        aid = next(d["approval_id"] for t, d in events if t == "approval_request")
        self.post(f"/api/chat/approvals/{aid}", {"decision": "allow"})
        self.assertTrue(wait_for(lambda: seen))
        self.assertEqual(seen, ["running"])

    # -- S5 : propositions encore `waiting` en fin de tour ------------------------------------

    def test_s5_proposition_waiting_a_la_fin_du_tour_devient_pending_puis_reprend(self):
        def behaviour(ctx, message):
            if message.startswith("[approbation]"):
                return resume_executes(ctx, message)
            threading.Thread(target=lambda: ctx.request_approval(MOCK_TOOL, MOCK_INPUT, "Jeudi", []),
                             daemon=True).start()
            while not self.service.approvals.list(ctx.session_id):
                time.sleep(0.02)
            ctx.emit("done", {"reason": "budget"})               # le backend s'arrête sans attendre

        self.start(approval_wait_s=30, backend_factory=scripted(behaviour))
        sid = self.new_session()
        _, _, events = self.stream(sid, "planifie")
        aid = next(d["approval_id"] for t, d in events if t == "approval_request")
        self.assertTrue(wait_for(lambda: self.get(f"/api/chat/approvals/{aid}")[2]["status"] == "pending"))
        resolved = [e["data"] for e in self.session_log(sid) if e["type"] == "approval_resolved"]
        self.assertIn({"approval_id": aid, "decision": "pending"}, resolved)
        self.assertEqual(self.post(f"/api/chat/approvals/{aid}", {"decision": "allow"})[0], 200)
        self.assertTrue(wait_for(lambda: tool_runs(self.session_log(sid)) == 1), "aucune reprise en file")
        self.assertTrue(wait_for(lambda: self.record(aid)["resume"] == "done"))

    # -- N5 : annulation pendant une autorisation --------------------------------------------

    def test_n5_annulation_apres_autorisation_met_l_execution_en_file(self):
        outcome = []

        def behaviour(ctx, message):
            if message.startswith("[approbation]"):
                return resume_executes(ctx, message)
            outcome.append(ctx.request_approval(MOCK_TOOL, MOCK_INPUT, "Jeudi", []))
            ctx.emit("done", {"reason": "interrupted"})

        self.start(approval_wait_s=30, backend_factory=scripted(behaviour))
        sid = self.new_session()
        box = self.stream_in_thread(sid, "planifie")
        self.assertTrue(box["approval"].wait(3))
        aid = self.service.approvals.list(sid)[0]["id"]
        self.service.approvals.resolve(aid, "allow")             # autorisée, mais le fil d'attente ne l'a pas vue
        self.service.interrupt(sid)
        self.assertTrue(box["finished"].wait(5))
        self.assertEqual(outcome, ["deny"])
        self.assertTrue(wait_for(lambda: tool_runs(self.session_log(sid)) == 1), "l'appel autorisé n'a jamais tourné")
        self.assertTrue(wait_for(lambda: self.record(aid)["resume"] == "done"))

    # -- N3 : limiteur de la route à jeton ------------------------------------------------------

    def test_n3_refus_global_n_enregistre_pas_d_essai_par_adresse(self):
        service = self.start(auth="proxy")
        service.approve_limiter = C.RateLimiter(5)
        service.approve_global = C.RateLimiter(1)
        hdrs = dict(CSRF, **{"X-Forwarded-For": "203.0.113.1"})
        self.assertEqual(self.request("POST", "/api/chat/approve/x.y/allow", {}, hdrs)[0], 404)
        self.assertEqual(self.request("POST", "/api/chat/approve/x.y/allow", {}, hdrs)[0], 429)
        self.assertEqual(self.request("POST", "/api/chat/approve/x.y/allow", {}, hdrs)[0], 429)
        self.assertEqual(len(service.approve_limiter._hits["203.0.113.1"]), 1)

    def test_n3_seaux_perimes_elagues(self):
        now = [0.0]
        limiter = C.RateLimiter(3, clock=lambda: now[0])
        for i in range(50):
            limiter.allow(f"10.0.0.{i}")
        self.assertEqual(len(limiter._hits), 50)
        now[0] = 120.0
        limiter.allow("10.9.9.9")
        self.assertEqual(list(limiter._hits), ["10.9.9.9"])

    # -- N9 : budget réservé par tour ------------------------------------------------------------

    def test_n9_deux_conversations_ne_recoivent_pas_chacune_tout_le_reste(self):
        release, grants = threading.Event(), {}

        def behaviour(ctx, message):
            grants[message] = ctx.config.get("turn_budget_eur")
            if message == "lent":
                release.wait(5)
            ctx.emit("done", {"reason": "end_turn"})

        self.start(daily_budget_eur=2.0, backend_factory=scripted(behaviour))
        first, second = self.new_session(), self.new_session()
        box = self.stream_in_thread(first, "lent")
        self.assertTrue(wait_for(lambda: "lent" in grants))
        _, _, events = self.stream(second, "autre")
        self.assertEqual(events[-2][0], "error")
        self.assertIn("réservé", events[-2][1]["message"])
        self.assertEqual(events[-1], ("done", {"reason": "budget"}))
        self.assertNotIn("autre", grants)
        release.set()
        self.assertTrue(box["finished"].wait(3))
        self.assertTrue(wait_for(lambda: not self.service._reserved))     # réservation libérée
        _, _, events = self.stream(second, "autre")
        self.assertEqual(events[-1], ("done", {"reason": "end_turn"}))
        self.assertAlmostEqual(grants["autre"], 2.0, places=4)

    def test_n9_plafond_par_tour_permet_la_concurrence_sans_depasser_le_reste(self):
        release, grants = threading.Event(), {}

        def behaviour(ctx, message):
            grants[message] = ctx.config.get("turn_budget_eur")
            if message == "lent":
                release.wait(5)
            ctx.emit("done", {"reason": "end_turn"})

        self.start(daily_budget_eur=0.8, turn_budget_max_eur=0.5, backend_factory=scripted(behaviour))
        first, second = self.new_session(), self.new_session()
        box = self.stream_in_thread(first, "lent")
        self.assertTrue(wait_for(lambda: "lent" in grants))
        self.stream(second, "autre")
        release.set()
        self.assertTrue(box["finished"].wait(3))
        self.assertAlmostEqual(grants["lent"], 0.5, places=4)
        self.assertAlmostEqual(grants["autre"], 0.3, places=4)


if __name__ == "__main__":
    unittest.main()
