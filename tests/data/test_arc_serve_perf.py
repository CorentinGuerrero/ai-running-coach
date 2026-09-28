"""Palier D — tableau de bord rapide : réindexation en arrière-plan, premier index
non bloquant, `/api/assumptions` séparé, gzip, revalidation ETag.

Serveur HTTP réel (port libre, fil local) sur un petit workspace écrit à la main —
pas de sous-processus : on peut ainsi espionner `Store.refresh`.
"""

from __future__ import annotations

import gzip
import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import arc_serve as S  # noqa: E402

TODAY = "2026-09-23"


def arc(data: dict) -> str:
    return f"# Titre\n\n```arc\n{json.dumps(data)}\n```\n\nTexte.\n"


def write_workspace(root: Path) -> Path:
    ws = root / "ws"
    for d in ("activities", "medical", "nutrition", "planning", "rapports"):
        (ws / d).mkdir(parents=True)
    for i, day in enumerate(("2026-09-20", "2026-09-21", "2026-09-22")):
        (ws / f"activities/{day}_running.md").write_text(
            arc({"arc": 1, "kind": "activity", "date": day, "sport": "running", "duration_s": 3600 + i * 60,
                 "distance_m": 10000 + i * 100}), encoding="utf-8")
    return ws


def report(ws: Path, title: str) -> None:
    (ws / "rapports/2026-09-23_rapport.md").write_text(
        arc({"arc": 1, "kind": "report", "date": TODAY, "report_type": "weekly", "title": title}), encoding="utf-8")


def get(url: str, headers: dict = None):
    req = urllib.request.Request(url, headers={"Host": url.split("/")[2], **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, res.read(), {k.lower(): v for k, v in res.headers.items()}
    except urllib.error.HTTPError as exc:
        with exc:
            return exc.code, exc.read(), {k.lower(): v for k, v in exc.headers.items()}


class LiveServer(unittest.TestCase):
    interval = 0.2

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="arc-serve-perf-"))
        self.ws = write_workspace(self.tmp)
        self.store = S.Store(self.ws, memory=True, today=TODAY, background=True)
        self.httpd = S.bind(0)
        port = self.httpd.server_address[1]
        S.Handler.store = self.store
        S.Handler.allowed_hosts = S.host_allowlist(port)
        self.base = f"http://127.0.0.1:{port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.store.stop_background()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.store.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def json(self, path: str):
        status, body, _ = get(self.base + path)
        self.assertEqual(status, 200, body)
        return json.loads(body)

    def wait_for(self, predicate, timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        return False


class TestBackgroundRefresh(LiveServer):
    def test_store_in_background_mode_does_not_index_in_constructor(self):
        self.assertFalse(self.store.ready.is_set())
        self.assertEqual(self.store.rows("SELECT COUNT(*) AS n FROM activity")[0]["n"], 0)

    def test_requests_never_trigger_a_reindex(self):
        self.store.start_background(interval=3600)
        self.assertEqual(len(self.json("/api/activities")["activities"]), 3)
        with mock.patch.object(self.store, "refresh", side_effect=AssertionError("réindexation dans une requête")):
            for path in ("/api/summary", "/api/activities", "/api/reports", "/api/week"):
                self.json(path)

    def test_new_file_is_picked_up_by_the_background_thread(self):
        self.store.start_background(interval=self.interval)
        self.assertEqual(self.json("/api/reports")["reports"], [])
        report(self.ws, "Bilan en arrière-plan")
        self.assertTrue(self.wait_for(
            lambda: [r["title"] for r in self.json("/api/reports")["reports"]] == ["Bilan en arrière-plan"]))

    def test_unchanged_passes_skip_metrics(self):
        self.store.start_background(interval=self.interval)
        self.assertTrue(self.store.wait_ready(10))
        self.assertTrue(self.wait_for(lambda: self.store.last_counts.get("metrics") == "skipped"))

    def test_background_error_does_not_kill_the_thread(self):
        calls = []
        real = S.I.index_workspace

        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("disque indisponible")
            return real(*args, **kwargs)

        with mock.patch.object(S.I, "index_workspace", side_effect=flaky), mock.patch("sys.stderr"):
            self.store.start_background(interval=self.interval)
            self.assertTrue(self.wait_for(lambda: len(calls) >= 2))
            self.assertTrue(self.wait_for(lambda: self.store.last_counts.get("indexed", 0) > 0))
        self.assertEqual(len(self.json("/api/activities")["activities"]), 3)


class TestFirstIndex(LiveServer):
    def test_healthz_and_static_answer_before_the_first_index(self):
        """Le serveur écoute avant la fin du premier index : la page s'affiche aussitôt."""
        self.assertEqual(get(self.base + "/healthz")[0], 200)
        status, body, _ = get(self.base + "/")
        self.assertEqual(status, 200)
        self.assertIn(b"js/app.js", body)

    def test_api_waits_for_the_first_index(self):
        gate = threading.Event()
        real = S.I.index_workspace

        def slow(*args, **kwargs):
            gate.wait(10)
            return real(*args, **kwargs)

        with mock.patch.object(S.I, "index_workspace", side_effect=slow):
            self.store.start_background(interval=3600)
            result = {}
            t = threading.Thread(target=lambda: result.setdefault("r", get(self.base + "/api/activities")))
            t.start()
            time.sleep(0.3)
            self.assertNotIn("r", result, "la requête doit attendre le premier index")
            gate.set()
            t.join(10)
        status, body, _ = result["r"]
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["activities"]), 3)

    def test_api_gives_up_with_503_if_first_index_never_ends(self):
        with mock.patch.object(S, "READY_TIMEOUT_S", 0.2):
            status, body, _ = get(self.base + "/api/summary")
        self.assertEqual(status, 503)
        self.assertIn("index", json.loads(body)["error"])


class TestPayloads(LiveServer):
    def setUp(self):
        super().setUp()
        self.store.start_background(interval=3600)
        self.assertTrue(self.store.wait_ready(10))

    def test_summary_no_longer_carries_assumptions(self):
        self.assertNotIn("assumptions", self.json("/api/summary"))

    def test_assumptions_route(self):
        assumptions = self.json("/api/assumptions")["assumptions"]
        self.assertIsInstance(assumptions, dict)
        self.assertIn("hr_zones", assumptions)

    def test_front_reads_assumptions_from_their_route(self):
        app = (REPO / "web/js/app.js").read_text(encoding="utf-8")
        self.assertNotIn("SUMMARY.assumptions", app)
        self.assertIn('api("assumptions")', app)

    def test_api_is_gzipped_when_accepted(self):
        status, body, headers = get(self.base + "/api/assumptions", {"Accept-Encoding": "gzip, deflate"})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("content-encoding"), "gzip")
        self.assertEqual(headers.get("cache-control"), "no-store")
        self.assertEqual(int(headers["content-length"]), len(body))
        self.assertIn("hr_zones", json.loads(gzip.decompress(body))["assumptions"])

    def test_api_is_plain_without_accept_encoding(self):
        status, body, headers = get(self.base + "/api/assumptions")
        self.assertIsNone(headers.get("content-encoding"))
        self.assertIn("hr_zones", json.loads(body)["assumptions"])

    def test_small_bodies_are_not_compressed(self):
        _, _, headers = get(self.base + "/healthz", {"Accept-Encoding": "gzip"})
        self.assertIsNone(headers.get("content-encoding"))

    def test_static_files_revalidate_with_etag(self):
        status, body, headers = get(self.base + "/js/app.js", {"Accept-Encoding": "gzip"})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("content-encoding"), "gzip")
        self.assertEqual(headers.get("cache-control"), "no-cache")
        self.assertEqual(gzip.decompress(body), (REPO / "web/js/app.js").read_bytes())
        etag = headers["etag"]
        status, body, headers = get(self.base + "/js/app.js", {"If-None-Match": etag})
        self.assertEqual((status, body), (304, b""))
        self.assertEqual(headers.get("etag"), etag)
        status, _, _ = get(self.base + "/js/app.js", {"If-None-Match": '"autre"'})
        self.assertEqual(status, 200)

    def test_head_on_static_sends_no_body(self):
        req = urllib.request.Request(self.base + "/js/app.js", method="HEAD",
                                     headers={"Host": self.base.split("/")[2], "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=10) as res:
            self.assertEqual(res.read(), b"")
            self.assertGreater(int(res.headers["Content-Length"]), 0)

    def test_security_headers_kept(self):
        _, _, headers = get(self.base + "/js/app.js", {"Accept-Encoding": "gzip"})
        self.assertIn("default-src 'self'", headers.get("content-security-policy", ""))
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")


class TestSynchronousStore(unittest.TestCase):
    """Usage bibliothèque (tests existants, `api_*` appelées directement) : inchangé."""

    def test_constructor_indexes_and_is_ready(self):
        tmp = Path(tempfile.mkdtemp(prefix="arc-serve-sync-"))
        try:
            store = S.Store(write_workspace(tmp), memory=True, today=TODAY)
            self.assertTrue(store.ready.is_set())
            self.assertEqual(len(S.api_activities(store, {})["activities"]), 3)
            self.assertEqual(S.api_assumptions(store, {})["assumptions"], store.meta("assumptions"))
            store.conn.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
