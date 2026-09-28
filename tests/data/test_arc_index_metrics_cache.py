"""Palier D — réindexation rapide du tableau de bord : `index_workspace(metrics_cache=…)`.

Deux raccourcis, réservés au processus longue durée (`arc_serve.Store`) :

1. passage sans changement → `compute_metrics` SAUTÉ (`metrics_fingerprint` inchangée) ;
2. passage avec changement → calculs par séance repris du `MetricsCache` quand leurs
   entrées n'ont pas bougé.

Ce que ces tests verrouillent : les deux raccourcis ne changent JAMAIS le résultat —
chaque état de base obtenu avec le cache est comparé, table par table, à celui d'un
recalcul intégral sur une base neuve (le comportement historique, toujours celui
des CLI).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
import arc_index as I  # noqa: E402
from tests.lib.synthetic import build  # noqa: E402

TODAY = "2026-09-23"


def dump(conn) -> dict:
    """Contenu complet de toutes les tables, trié : deux bases égales ⇔ mêmes données."""
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {t: sorted((tuple(r) for r in conn.execute(f'SELECT * FROM "{t}"').fetchall()), key=repr) for t in tables}


class MetricsCacheCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = Path(tempfile.mkdtemp(prefix="arc-mcache-tpl-"))
        build(cls.template / "ws", days=35, today=date.fromisoformat(TODAY), sport="trail", seed=11,
              with_samples=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.template, ignore_errors=True)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="arc-mcache-"))
        self.ws = self.tmp / "ws"
        shutil.copytree(self.template / "ws", self.ws)
        self.conn = I.open_db(self.ws, memory=True)
        # Témoin : MÊMES passages, sans cache (comportement historique des CLI). Comparer à
        # une base neuve ne suffirait pas : après une suppression, un index incrémental
        # garde d'autres rowid qu'une reconstruction, cache ou pas.
        self.shadow = I.open_db(self.ws, memory=True)
        self.cache = I.MetricsCache()

    def tearDown(self):
        self.conn.close()
        self.shadow.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def index(self, today=TODAY):
        return I.index_workspace(self.conn, self.ws, today, self.cache)

    def start(self, today=TODAY):
        """Premier passage, avec cache et témoin."""
        I.index_workspace(self.shadow, self.ws, today)
        return self.index(today)

    def assertSameAsFullRecompute(self, today=TODAY):
        """État obtenu avec cache/saut == état du témoin recalculé intégralement."""
        I.index_workspace(self.shadow, self.ws, today)
        mine, ref = dump(self.conn), dump(self.shadow)
        self.assertEqual(sorted(mine), sorted(ref))
        for table in ref:
            if table == "meta":
                continue  # porte l'empreinte, identique par construction ; comparée à part
            self.assertEqual(mine[table], ref[table], f"table {table} diverge du recalcul intégral")
        self.assertEqual(mine["meta"], ref["meta"])


class TestFixture(MetricsCacheCase):
    def test_workspace_has_run_activities_with_samples(self):
        """Garde-fou du jeu de test : sans séances à échantillons, le cache ne serait pas exercé."""
        self.start()
        with_samples = self.conn.execute(
            "SELECT COUNT(DISTINCT a.id) FROM activity a JOIN activity_sample s "
            "ON s.garmin_activity_id = a.garmin_activity_id").fetchone()[0]
        self.assertGreaterEqual(with_samples, 5)
        self.assertGreater(len(self.cache), 0)


class TestSkipWhenUnchanged(MetricsCacheCase):
    def test_second_pass_skips_metrics_and_keeps_tables(self):
        self.assertEqual(self.start()["metrics"], "computed")
        before = dump(self.conn)
        with mock.patch.object(I, "compute_metrics", side_effect=AssertionError("ne doit pas être appelé")):
            counts = self.index()
        self.assertEqual(counts["metrics"], "skipped")
        self.assertEqual(dump(self.conn), before)
        self.assertSameAsFullRecompute()

    def test_without_cache_always_recomputes(self):
        """CLI, synchronisation, tests existants : comportement historique inchangé."""
        I.index_workspace(self.conn, self.ws, TODAY)
        with mock.patch.object(I, "compute_metrics", wraps=I.compute_metrics) as spy:
            counts = I.index_workspace(self.conn, self.ws, TODAY)
        self.assertEqual(counts["metrics"], "computed")
        spy.assert_called_once()

    def test_fingerprint_written_without_cache_is_honoured(self):
        """Base partagée : un index fait par la CLI (sans cache) suffit au tableau de bord."""
        I.index_workspace(self.conn, self.ws, TODAY)
        self.assertEqual(self.start()["metrics"], "skipped")

    def test_new_day_recomputes(self):
        """La série quotidienne et les fenêtres glissantes dépendent de la date."""
        self.start()
        counts = self.index(today="2026-09-24")
        self.assertEqual(counts["metrics"], "computed")
        self.assertSameAsFullRecompute(today="2026-09-24")

    def test_today_none_uses_the_calendar_date(self):
        """Sans `--today` (production), l'empreinte porte la date du jour : minuit passé,
        le passage suivant recalcule."""
        self.start(today=None)
        self.assertEqual(self.index(today=None)["metrics"], "skipped")
        conf = I.settings(I.load_config(self.ws))
        stored = self.conn.execute("SELECT value FROM meta WHERE key = 'metrics_fingerprint'").fetchone()[0]
        self.assertEqual(stored, I.metrics_fingerprint(self.conn, conf, date.today().isoformat()))
        self.assertNotEqual(stored, I.metrics_fingerprint(self.conn, conf, "2031-01-01"))

    def test_markdown_change_recomputes(self):
        self.start()
        (self.ws / "medical/2026-09-23_health.md").write_text(
            '# Santé\n\n```arc\n{"arc": 1, "kind": "health", "date": "2026-09-23", "hrv_ms": 71, '
            '"weight_kg": 70.5}\n```\n', encoding="utf-8")
        self.assertEqual(self.index()["metrics"], "computed")
        self.assertSameAsFullRecompute()

    def test_removed_file_recomputes(self):
        self.start()
        victim = sorted((self.ws / "activities").glob("*_trail.md"))[-1]
        victim.unlink()
        self.assertEqual(self.index()["metrics"], "computed")
        self.assertSameAsFullRecompute()

    def test_config_change_recomputes(self):
        self.start()
        with (self.ws / "config/workspace.user.toml").open("a", encoding="utf-8") as fh:
            fh.write("\n[metrics]\nclimb_min_gain_m = 15\n")
        self.assertEqual(self.index()["metrics"], "computed")
        self.assertSameAsFullRecompute()

    def test_code_change_recomputes(self):
        """Une base sur disque écrite par une autre version du moteur n'est jamais réutilisée telle quelle."""
        self.start()
        with mock.patch.object(I, "_CODE_DIGEST", "une-autre-version"):
            self.assertEqual(self.index()["metrics"], "computed")


class TestPerActivityCache(MetricsCacheCase):
    def test_unrelated_change_reuses_every_activity(self):
        """Un nouveau rapport ne touche aucune séance : zéro recalcul d'échantillons."""
        self.start()
        (self.ws / "rapports/2026-09-23_rapport.md").write_text(
            '# Bilan\n\n```arc\n{"arc": 1, "kind": "report", "date": "2026-09-23", "report_type": "weekly", '
            '"title": "Bilan"}\n```\n', encoding="utf-8")
        with mock.patch.object(I, "samples", wraps=I.samples) as loaded, \
                mock.patch.object(I, "_sample_derived_metrics", wraps=I._sample_derived_metrics) as computed:
            self.assertEqual(self.index()["metrics"], "computed")
        self.assertEqual(computed.call_count, 0)
        self.assertEqual(loaded.call_count, 0, "aucun échantillon ne doit être relu")
        self.assertEqual(self.cache.misses, 0)
        self.assertGreater(self.cache.hits, 0)
        self.assertSameAsFullRecompute()

    def test_changed_samples_recompute_only_that_activity(self):
        self.start()
        fit = sorted((self.ws / "activities/fit").glob("*.json"))[0]
        raw = fit.read_text(encoding="utf-8")
        # Même structure, un échantillon de moins : le contenu change, pas le format.
        import json
        data = json.loads(raw)
        records = data["records"] if isinstance(data, dict) else data
        del records[len(records) // 2]
        fit.write_text(json.dumps(data), encoding="utf-8")
        with mock.patch.object(I, "_sample_derived_metrics", wraps=I._sample_derived_metrics) as computed:
            self.index()
        self.assertEqual(computed.call_count, 1)
        self.assertSameAsFullRecompute()

    def test_weight_change_invalidates_energy_only(self):
        """La dépense dépend du poids à la date de la séance ; les autres calculs non."""
        self.start()
        first = self.conn.execute(
            "SELECT MIN(date) FROM activity WHERE garmin_activity_id IS NOT NULL").fetchone()[0]
        # Pesée datée AVANT toutes les séances : change le poids résolu pour celles qui
        # n'avaient pas de pesée plus récente, ou aucune si elles en ont une — dans tous
        # les cas le résultat doit égaler le recalcul intégral.
        day = date.fromisoformat(first).replace(day=1).isoformat()
        (self.ws / f"medical/{day}_health.md").write_text(
            f'# Santé\n\n```arc\n{{"arc": 1, "kind": "health", "date": "{day}", "weight_kg": 91.0}}\n```\n',
            encoding="utf-8")
        with mock.patch.object(I, "_sample_derived_metrics", wraps=I._sample_derived_metrics) as computed:
            self.index()
        self.assertEqual(computed.call_count, 0, "le poids n'entre pas dans les calculs hors dépense")
        self.assertSameAsFullRecompute()

    def test_profile_change_recomputes_hr_dependent_metrics(self):
        """FC au seuil modifiée → bornes de zones différentes → clé différente pour toutes les séances."""
        self.start()
        profile = self.ws / "planning/Runner_Profile.md"
        text = profile.read_text(encoding="utf-8")
        import re
        changed = re.sub(r"(\*\*FC au seuil\*\*\s*:\s*)(\d+)", lambda m: m.group(1) + str(int(m.group(2)) - 7), text, count=1)
        if changed == text:
            self.skipTest("profil synthétique sans FC au seuil lisible")
        profile.write_text(changed, encoding="utf-8")
        with mock.patch.object(I, "_sample_derived_metrics", wraps=I._sample_derived_metrics) as computed:
            self.index()
        self.assertGreater(computed.call_count, 0)
        self.assertSameAsFullRecompute()

    def test_cache_is_pruned_to_current_activities(self):
        self.start()
        size = len(self.cache)
        for md in sorted((self.ws / "activities").glob("*_trail.md"))[:3]:
            md.unlink()
        self.index()
        self.assertLess(len(self.cache), size)
        self.assertSameAsFullRecompute()

    def test_failed_activity_is_not_cached_and_matches_full_recompute(self):
        """Défense en profondeur (#46) intacte : l'échec d'un calcul ne se fige pas dans le cache."""
        boom = mock.patch.object(I.VC, "detect_climbs", side_effect=RuntimeError("détecteur en panne"))
        with mock.patch.dict("os.environ", {"ARC_STRICT_METRICS": "0"}), boom, \
                mock.patch("sys.stderr"):
            self.start()
        self.assertEqual(len(self.cache), len([k for k in self.cache._entries if k.startswith("energy:")]))
        # Détecteur réparé + changement quelconque : les séances sont recalculées, pas relues d'un cache vide de sens.
        (self.ws / "rapports/2026-09-23_rapport.md").write_text(
            '# Bilan\n\n```arc\n{"arc": 1, "kind": "report", "date": "2026-09-23", "report_type": "weekly", '
            '"title": "Bilan"}\n```\n', encoding="utf-8")
        self.index()
        self.assertSameAsFullRecompute()


if __name__ == "__main__":
    unittest.main()
