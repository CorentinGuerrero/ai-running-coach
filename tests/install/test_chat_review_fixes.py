"""Palier A — corrections de revue du service de chat (`scripts/arc_chat.py`).

Course de fin d'attente, expirations journalisées, file de reprises, budget du tour,
langue, limite de débit par adresse, boutons ntfy réservés aux sujets à accès contrôlé.
Même bac à sable que `test_chat_service.py` (serveur réel, backend scripté ou `mock`).
"""

from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import arc_chat as C  # noqa: E402
from arc_chat_backend import BackendError, ChatBackend  # noqa: E402
from arc_chat_mock import TOOL_INPUT as MOCK_INPUT  # noqa: E402
from arc_chat_mock import TOOL as MOCK_TOOL  # noqa: E402
from tests.install.test_chat_service import CSRF, ChatCase, FakeNtfy, wait_for  # noqa: E402


class ScriptedBackend(ChatBackend):
    """Backend de test : `behaviour(ctx, message)` fait ce qu'on veut, le service fait le reste."""

    name = "scripted"
    behaviour = None

    def run_turn(self, ctx, user_message):
        type(self).behaviour(ctx, user_message)


def scripted(fn):
    return type("S", (ScriptedBackend,), {"behaviour": staticmethod(fn)})


def propose_then_pending(ctx, message):
    """Premier tour : une proposition Garmin qui reste `pending` ; reprise : l'exécute."""
    if message.startswith("[approbation]"):
        if ctx.decide(MOCK_TOOL, MOCK_INPUT) == "allow":
            ctx.emit("tool_start", {"id": "t2", "name": MOCK_TOOL, "summary": "Planification"})
        ctx.emit("done", {"reason": "end_turn"})
        return
    if ctx.decide(MOCK_TOOL, MOCK_INPUT) == "ask":
        ctx.request_approval(MOCK_TOOL, MOCK_INPUT, "Jeudi : EF 45 min", [])
    ctx.emit("done", {"reason": "pending_approval"})


class TestReviewFixes(ChatCase):
    def session_log(self, sid):
        return self.get(f"/api/chat/sessions/{sid}")[2]["events"]

    def pending_session(self, **over):
        self.start(approval_wait_s=0.2, **over)
        sid = self.new_session()
        _, _, events = self.stream(sid, "planifie")
        aid = next(d["approval_id"] for t, d in events if t == "approval_request")
        self.assertEqual(self.get(f"/api/chat/approvals/{aid}")[2]["status"], "pending")
        return sid, aid

    # -- 7 : course au bord de l'attente ---------------------------------------------

    def test_decision_pile_au_bord_de_l_attente_n_est_pas_perdue(self):
        self.start(approval_wait_s=0.3)
        sid = self.new_session()
        real = C.ApprovalStore.mark_pending

        def racing(store, approval_id):
            # Entrelacement forcé : la décision est écrite dans le magasin juste avant
            # `mark_pending`, mais la boîte du waiter n'est pas encore remplie.
            store.resolve(approval_id, "allow")
            return real(store, approval_id)

        C.ApprovalStore.mark_pending = racing
        self.addCleanup(lambda: setattr(C.ApprovalStore, "mark_pending", real))
        _, _, events = self.stream(sid, "planifie ma séance")
        names = [d.get("name") for t, d in events if t == "tool_start"]
        self.assertIn(MOCK_TOOL, names, "l'approbation a été perdue (retour « deny »)")
        self.assertEqual(events[-1], ("done", {"reason": "end_turn"}))
        aid = next(d["approval_id"] for t, d in events if t == "approval_request")
        self.assertEqual(self.get(f"/api/chat/approvals/{aid}")[2]["status"], "allowed")
        time.sleep(0.2)                                   # pas de reprise en double : un seul appel exécuté
        log = self.session_log(sid)
        self.assertEqual(sum(1 for e in log if e["type"] == "tool_start" and e["data"]["name"] == MOCK_TOOL), 1)

    # -- 8 : expirations journalisées ---------------------------------------------------

    def test_expiration_decouverte_par_une_lecture_est_journalisee(self):
        sid, aid = self.pending_session(approval_ttl_s=0.4)
        time.sleep(0.5)
        self.assertEqual(self.get(f"/api/chat/approvals/{aid}")[2]["status"], "expired")     # pas de balayage
        resolved = [e["data"] for e in self.session_log(sid) if e["type"] == "approval_resolved"]
        self.assertEqual(resolved[-1], {"approval_id": aid, "decision": "expired"})
        self.assertEqual([r["decision"] for r in resolved].count("expired"), 1)              # une seule fois

    def test_expiration_decouverte_par_la_liste_ou_une_decision(self):
        sid, aid = self.pending_session(approval_ttl_s=0.4)
        time.sleep(0.5)
        self.get("/api/chat/sessions")                                                        # session_summary → list
        self.assertEqual(self.post(f"/api/chat/approvals/{aid}", {"decision": "allow"})[0], 410)
        resolved = [e["data"] for e in self.session_log(sid) if e["type"] == "approval_resolved"]
        self.assertEqual([r["decision"] for r in resolved].count("expired"), 1)

    # -- 6 : reprises ---------------------------------------------------------------------

    def test_approbation_tardive_pendant_un_autre_tour_est_mise_en_file(self):
        sid, aid = self.pending_session()
        box = self.stream_in_thread(sid, "réponse lente svp")                                 # occupe la session
        self.assertTrue(wait_for(lambda: self.get(f"/api/chat/sessions/{sid}")[2]["running"]))
        self.assertEqual(self.post(f"/api/chat/approvals/{aid}", {"decision": "allow"})[0], 200)
        time.sleep(0.4)                                   # l'ancienne attente de 120 s ne faisait que journaliser
        self.assertEqual(sum(1 for e in self.session_log(sid)
                             if e["type"] == "user_message" and e["data"].get("synthetic")), 0)
        self.assertEqual(len(self.service.approvals.queued_resumes()), 1)
        self.post(f"/api/chat/sessions/{sid}/interrupt")
        self.assertTrue(box["finished"].wait(3))

        def resumed():
            log = self.session_log(sid)
            return any(e["type"] == "tool_start" and e["data"]["name"] == MOCK_TOOL for e in log)

        self.assertTrue(wait_for(resumed, 5), "la reprise en file n'a jamais été lancée")
        self.assertEqual(self.get(f"/api/chat/approvals/{aid}")[2]["status"], "allowed")
        self.assertTrue(wait_for(lambda: self.service.approvals.queued_resumes() == []))

    def test_reprise_impossible_budget_epuise(self):
        sid, aid = self.pending_session(daily_budget_eur=1.0)
        self.service.spend.add(5.0)
        self.assertEqual(self.post(f"/api/chat/approvals/{aid}", {"decision": "allow"})[0], 200)
        self.assertTrue(wait_for(lambda: self.get(f"/api/chat/approvals/{aid}")[2]["status"] == "unexecuted"))
        log = self.session_log(sid)
        self.assertIn("error", [e["type"] for e in log])
        resolved = [e["data"] for e in log if e["type"] == "approval_resolved"]
        self.assertEqual(resolved[-1], {"approval_id": aid, "decision": "unexecuted"})

    def test_reprise_impossible_erreur_du_backend(self):
        def behaviour(ctx, message):
            if message.startswith("[approbation]"):
                raise BackendError("Fournisseur injoignable.")
            propose_then_pending(ctx, message)

        self.start(approval_wait_s=0.2, backend_factory=scripted(behaviour))
        sid = self.new_session()
        _, _, events = self.stream(sid, "planifie")
        aid = next(d["approval_id"] for t, d in events if t == "approval_request")
        self.post(f"/api/chat/approvals/{aid}", {"decision": "allow"})
        self.assertTrue(wait_for(lambda: self.get(f"/api/chat/approvals/{aid}")[2]["status"] == "unexecuted"))
        errors = [e["data"]["message"] for e in self.session_log(sid) if e["type"] == "error"]
        self.assertEqual(errors, ["Fournisseur injoignable."])

    def test_reprise_ou_le_modele_n_execute_pas_l_appel(self):
        def behaviour(ctx, message):
            if message.startswith("[approbation]"):
                ctx.emit("text_delta", {"text": "Je préfère ne rien faire."})
                ctx.emit("done", {"reason": "end_turn"})
                return
            propose_then_pending(ctx, message)

        self.start(approval_wait_s=0.2, backend_factory=scripted(behaviour))
        sid = self.new_session()
        _, _, events = self.stream(sid, "planifie")
        aid = next(d["approval_id"] for t, d in events if t == "approval_request")
        self.post(f"/api/chat/approvals/{aid}", {"decision": "allow"})
        self.assertTrue(wait_for(lambda: self.get(f"/api/chat/approvals/{aid}")[2]["status"] == "unexecuted"))
        errors = [e["data"]["message"] for e in self.session_log(sid) if e["type"] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("approuvée mais non exécutée", errors[0])

    def test_une_approbation_autorise_une_seule_execution(self):
        # Revue : le hash pré-approuvé n'était jamais retiré ; un second appel identique dans la
        # reprise passait sans nouvelle carte (double planification Garmin).
        verdicts = []

        def behaviour(ctx, message):
            if message.startswith("[approbation]"):
                verdicts.append(ctx.decide(MOCK_TOOL, MOCK_INPUT))
                verdicts.append(ctx.decide(MOCK_TOOL, MOCK_INPUT))   # répétition du même appel
                ctx.emit("done", {"reason": "end_turn"})
                return
            propose_then_pending(ctx, message)

        self.start(approval_wait_s=0.2, backend_factory=scripted(behaviour))
        sid = self.new_session()
        _, _, events = self.stream(sid, "planifie")
        aid = next(d["approval_id"] for t, d in events if t == "approval_request")
        self.post(f"/api/chat/approvals/{aid}", {"decision": "allow"})
        self.assertTrue(wait_for(lambda: len(verdicts) == 2))
        self.assertEqual(verdicts, ["allow", "ask"])

    def test_approbation_acceptee_non_executee_reprend_au_demarrage(self):
        sid, aid = self.pending_session()
        path = self.ws / ".arc/chat/approvals.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data[aid].update(status="allowed", resume="queued")            # arrêt brutal juste après l'acceptation
        path.write_text(json.dumps(data), encoding="utf-8")
        self.start()                                                   # nouveau service, même workspace
        self.assertTrue(wait_for(lambda: any(
            e["type"] == "tool_start" and e["data"]["name"] == MOCK_TOOL for e in self.session_log(sid))),
            "l'approbation acceptée n'a pas été exécutée au démarrage")
        self.assertTrue(wait_for(lambda: json.loads(path.read_text(encoding="utf-8"))[aid]["resume"] == "done"))

    # -- 12 : budget du tour, coût enregistré malgré l'erreur ------------------------------

    def test_budget_restant_transmis_au_backend_sans_muter_la_config_partagee(self):
        seen = []

        def behaviour(ctx, message):
            seen.append(ctx.config.get("turn_budget_eur"))
            ctx.emit("done", {"reason": "end_turn"})

        self.start(daily_budget_eur=2.0, turn_budget_max_eur=0.0, backend_factory=scripted(behaviour))
        self.service.spend.add(0.5)
        self.stream(self.new_session(), "salut")
        self.assertEqual(len(seen), 1)
        self.assertAlmostEqual(seen[0], 1.5, places=4)
        self.assertNotIn("turn_budget_eur", self.service.cfg)

    def test_cout_enregistre_meme_si_le_backend_echoue_ensuite(self):
        def behaviour(ctx, message):
            ctx.emit("usage", {"input_tokens": 1, "output_tokens": 1, "cache_read_tokens": 0, "cost_eur": 0.25})
            raise BackendError("Crédit épuisé.")

        self.start(backend_factory=scripted(behaviour))
        sid = self.new_session()
        _, _, events = self.stream(sid, "salut")
        self.assertEqual(events[-1][0], "error")
        self.assertAlmostEqual(self.service.spend.spent(), 0.25)
        self.assertAlmostEqual(self.get(f"/api/chat/sessions/{sid}")[2]["cost_eur"], 0.25)

    # -- nits ------------------------------------------------------------------------------

    def test_langue_du_tour_vient_de_language_documents(self):
        langs = []

        def behaviour(ctx, message):
            langs.append(ctx.language)
            ctx.emit("done", {"reason": "end_turn"})

        (self.ws / "config").mkdir()
        (self.ws / "config/workspace.user.toml").write_text(
            '[language]\ndocuments = "en"\n\n[chat]\nlanguage = "de"\n', encoding="utf-8")
        self.start(backend_factory=scripted(behaviour), language="de")   # `[chat].language` ne compte pas
        self.stream(self.new_session(), "hi")
        self.assertEqual(langs, ["en"])

    def test_langue_par_defaut_fr(self):
        langs = []

        def behaviour(ctx, message):
            langs.append(ctx.language)
            ctx.emit("done", {"reason": "end_turn"})

        self.start(backend_factory=scripted(behaviour))
        self.stream(self.new_session(), "salut")
        self.assertEqual(langs, ["fr"])

    def test_limite_des_actions_rapides_par_adresse_cliente(self):
        service = self.start(auth="proxy")
        service.approve_limiter = C.RateLimiter(2)
        service.approve_global = C.RateLimiter(3)

        def hit(ip):
            return self.request("POST", "/api/chat/approve/x.y/allow", {}, dict(CSRF, **{"X-Forwarded-For": ip}))[0]

        self.assertEqual([hit("203.0.113.1"), hit("203.0.113.1"), hit("203.0.113.1")], [404, 404, 429])
        self.assertEqual(hit("203.0.113.2"), 404)                        # une autre adresse n'est pas touchée
        self.assertEqual(hit("203.0.113.2"), 429)                        # plafond global (3) atteint
        # un en-tête forgé à gauche n'aide pas : seule la dernière entrée (ajoutée par le proxy) compte
        service.approve_limiter, service.approve_global = C.RateLimiter(1), C.RateLimiter(100)
        self.assertEqual(hit("198.51.100.9, 203.0.113.7"), 404)
        self.assertEqual(hit("198.51.100.10, 203.0.113.7"), 429)

    def test_limite_globale_par_defaut_est_un_plafond(self):
        self.assertEqual(C.APPROVE_GLOBAL_PER_MIN, 120)
        self.assertLess(C.APPROVE_PER_IP_PER_MIN, C.APPROVE_GLOBAL_PER_MIN)


class TestNtfyReviewFixes(ChatCase):
    def setUp(self):
        super().setUp()
        self.ntfy = FakeNtfy()
        self.addCleanup(self.ntfy.close)

    def notif(self, token_file=True):
        path = self.ws / "ntfy.token"
        path.write_text("tk-test\n", encoding="utf-8")
        return {"provider": "ntfy", "ntfy_url": self.ntfy.url, "ntfy_topic": "coach-test",
                "ntfy_token_file": str(path) if token_file else ""}

    def test_sans_fichier_token_pas_de_boutons_rapides_et_un_seul_avertissement(self):
        logs = []
        C.log = logs.append                                              # restauré par le nettoyage de setUp
        self.start(notif=self.notif(token_file=False), public_url="https://coach.example.com",
                   approval_wait_s=0.2)
        sid = self.new_session()
        for _ in range(2):
            self.stream(sid, "planifie")
        sent = self.ntfy.wait(2)
        self.assertEqual(len(sent), 2)
        for message in sent:
            self.assertIn("view, Ouvrir", message["headers"]["Actions"])
            self.assertNotIn("http,", message["headers"]["Actions"])
            self.assertNotIn("/approve/", message["headers"]["Actions"])
        self.assertEqual(self.service.approvals.list()[0]["token_hashes"], {})            # aucun jeton créé
        warnings = [line for line in logs if "ntfy_token_file" in line]
        self.assertEqual(len(warnings), 1, warnings)                                        # une seule fois

    def test_avec_fichier_token_boutons_rapides(self):
        self.start(notif=self.notif(), public_url="https://coach.example.com", approval_wait_s=0.2)
        self.stream(self.new_session(), "planifie")
        actions = self.ntfy.wait(1)[-1]["headers"]["Actions"]
        self.assertIn("http, Appliquer", actions)
        self.assertRegex(actions, r"/api/chat/approve/[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/allow")

    def test_reprise_impossible_envoie_un_ntfy_sans_valeur_de_sante(self):
        self.start(notif=self.notif(), public_url="https://coach.example.com", approval_wait_s=0.2,
                   daily_budget_eur=1.0)
        sid = self.new_session()
        _, _, events = self.stream(sid, "planifie")
        aid = next(d["approval_id"] for t, d in events if t == "approval_request")
        self.ntfy.wait(1)
        self.service.spend.add(5.0)
        self.post(f"/api/chat/approvals/{aid}", {"decision": "allow"})
        sent = self.ntfy.wait(2)
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[1]["body"], "Proposition approuvée mais non exécutée : Jeudi 1er octobre : footing EF 45 min")
        self.assertIn("non exécutée", sent[1]["headers"]["Title"])
        self.assertEqual(self.get(f"/api/chat/approvals/{aid}")[2]["status"], "unexecuted")


if __name__ == "__main__":
    unittest.main()
