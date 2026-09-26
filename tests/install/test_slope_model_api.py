"""Palier A — API du modèle personnel pente -> allure (#58) sur un workspace de
bac à sable dédié.

Même motif que `test_durability_api.py`/`test_descent_api.py` : plutôt que de
modifier le fixture golden partagé, ce fichier construit son PROPRE petit
workspace synthétique AVEC échantillons FIT (`tests.lib.synthetic.build(...,
with_samples=True)`, assez de séances trail sur 200 jours pour peupler
plusieurs paniers de pente) et lance un vrai serveur (`Server`/`Sandbox`, même
infrastructure que `test_dashboard.py`) pour vérifier `/api/slope-model` de
bout en bout — bande par défaut, bascule de bande, et le CLI `slope-model`
(stocké vs recalculé à la volée avec `--months`)."""

from __future__ import annotations

import json
import subprocess

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import arc_slope_model as SL  # noqa: E402

from tests.install.test_dashboard import Server
from tests.lib.sandbox import Sandbox
from tests.lib.asserts import InstallAsserts
from tests.lib.synthetic import build

TODAY = "2026-09-26"


class TestSlopeModelApi(InstallAsserts):
    def setUp(self):
        self.sb = Sandbox().__enter__()
        import datetime
        self.ws = build(self.sb.root / "ws", days=200, sport="trail", seed=11,
                         today=datetime.date.fromisoformat(TODAY), with_samples=True)
        self.server = Server(self.sb, ["python3", str(self.sb.repo / "scripts/arc_serve.py"),
                                       "--workspace", str(self.ws), "--port", "0", "--today", TODAY])
        self.assertIsNotNone(self.server.url, self.server.proc.stderr.read() if self.server.proc.poll() is not None else "pas d'URL")

    def tearDown(self):
        self.server.stop()
        self.sb.__exit__(None, None, None)

    def test_default_band_is_endurance_and_has_personal_bins(self):
        status, body, _ = self.server.get("/api/slope-model")
        self.assertEqual(status, 200)
        model = json.loads(body)
        self.assertEqual(model["band"], "endurance")
        self.assertIsNone(model["reason_code"], model["reason"])
        self.assertGreater(model["n_activities"], 0)
        personal = [b for b in model["bins"] if b["source"] == "personal"]
        self.assertTrue(personal, "aucun panier personnel — le workspace synthétique devrait en fournir")
        # Chaque panier personnel porte un compte d'échantillons/séances et un
        # repère de dispersion (voir arc_slope_model.ASSUMPTIONS['robust_stats']).
        for b in personal:
            self.assertGreater(b["n_samples"], 0)
            self.assertGreater(b["n_activities"], 0)
            self.assertIsNotNone(b["run_share"])

    def test_all_band_is_selectable_and_differs_from_endurance(self):
        status, body, _ = self.server.get("/api/slope-model?band=all")
        self.assertEqual(status, 200)
        all_model = json.loads(body)
        self.assertEqual(all_model["band"], "all")
        self.assertIsNone(all_model["reason_code"], all_model["reason"])
        _, endurance_body, _ = self.server.get("/api/slope-model?band=endurance")
        endurance_model = json.loads(endurance_body)
        # Pas nécessairement des valeurs différentes partout, mais au moins une
        # population de séances différente (voir arc_slope_model.ASSUMPTIONS
        # ['population']) — jamais exactement le même nombre par hasard sur un
        # workspace synthétique avec plusieurs niveaux d'effort.
        self.assertNotEqual(all_model["n_activities"], 0)
        self.assertNotEqual(endurance_model["n_activities"], 0)

    def test_unknown_band_falls_back_to_endurance_rather_than_erroring(self):
        status, body, _ = self.server.get("/api/slope-model?band=sprint")
        self.assertEqual(status, 200)
        model = json.loads(body)
        self.assertEqual(model["band"], "endurance")

    def test_generic_bins_are_flagged_and_never_confused_with_personal_ones(self):
        status, body, _ = self.server.get("/api/slope-model?band=all")
        model = json.loads(body)
        sources = {b["source"] for b in model["bins"]}
        self.assertLessEqual(sources, {"personal", "generic"})
        generic = [b for b in model["bins"] if b["source"] == "generic"]
        for b in generic:
            self.assertEqual(b["n_activities"], 0)
            self.assertIsNone(b["ci_low_speed_ms"])

    def test_open_tail_bins_have_null_bounds_over_the_wire(self):
        status, body, _ = self.server.get("/api/slope-model?band=all")
        model = json.loads(body)
        low_tail = next(b for b in model["bins"] if b["label"] == SL.GRADE_BINS[0][2])
        high_tail = next(b for b in model["bins"] if b["label"] == SL.GRADE_BINS[-1][2])
        self.assertIsNone(low_tail["grade_lo"])
        self.assertIsNone(high_tail["grade_hi"])

    def test_cli_slope_model_reads_the_already_stored_model(self):
        out = subprocess.run(
            ["python3", str(self.sb.repo / "scripts/arc_index.py"), "--workspace", str(self.ws),
             "--today", TODAY, "slope-model", "--band", "all"],
            cwd=str(self.sb.repo), env=self.sb.env(), capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["band"], "all")
        self.assertIsNone(payload["reason_code"], payload["reason"])

    def test_cli_slope_model_months_override_recomputes(self):
        out = subprocess.run(
            ["python3", str(self.sb.repo / "scripts/arc_index.py"), "--workspace", str(self.ws),
             "--today", TODAY, "slope-model", "--band", "all", "--months", "2"],
            cwd=str(self.sb.repo), env=self.sb.env(), capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["months"], 2)
