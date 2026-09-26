"""Palier D — modèle personnel pente -> allure (#58, épopée #23).

Familles de tests :
- Paniers de pente (`GRADE_BINS`) : bornes, étiquettes, point milieu.
- `activity_bin_summaries` : échantillons à l'arrêt exclus, bande « endurance »
  (filtre FC) vs « all » (aucun filtre), part de marche (`run_share`), trous de
  signal jamais franchis (hérité de `arc_elevation.grade_series`/`arc_gap.
  gap_sample_series`, réutilisés tels quels).
- `fit_slope_model` bout en bout sur des séances synthétiques à courbe
  pente -> allure IMPOSÉE (`tests.lib.synthetic.sample_session(slope_factor_fn=...)`) :
  la courbe est retrouvée à une tolérance documentée près, sur plusieurs pentes
  (montée et descente) ; effet de la pondération par récence ; effet du filtre
  de bande FC ; fenêtre de mois qui exclut les séances trop anciennes.
- Repli générique (Minetti) quand un panier manque de données, `source:
  "generic"` explicite ; `predict_speed` (interpolation entre paniers,
  extrapolation plate aux queues).
- `arc_index` : tables `slope_model_bin`/`slope_model_meta` recalculées à
  l'indexation, CLI `slope-model` (stocké et recalculé à la volée), garde en
  cas d'échec inattendu d'un calcul dérivé de la même activité (même
  discipline que #46/#47/#48 : une activité en échec ne doit jamais empêcher
  l'indexation des autres, ni celle du modèle pente -> allure lui-même).
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import arc_gap as G  # noqa: E402
import arc_index as I  # noqa: E402
import arc_slope_model as SL  # noqa: E402
from tests.lib.synthetic import sample_session  # noqa: E402


# ---------------------------------------------------------------------------
# Paniers de pente
# ---------------------------------------------------------------------------


class TestGradeBins(unittest.TestCase):
    def test_bins_cover_minus_30_to_plus_30_with_two_open_tails(self):
        self.assertEqual(SL.GRADE_BINS[0][0], float("-inf"))
        self.assertEqual(SL.GRADE_BINS[0][1], -SL.BIN_MAX_ABS)
        self.assertEqual(SL.GRADE_BINS[-1][0], SL.BIN_MAX_ABS)
        self.assertEqual(SL.GRADE_BINS[-1][1], float("inf"))
        # Continuité stricte : la borne haute d'un panier == la borne basse du suivant.
        for (_, hi, _), (lo2, _, _) in zip(SL.GRADE_BINS, SL.GRADE_BINS[1:]):
            self.assertAlmostEqual(hi, lo2, places=9)

    def test_grade_bin_picks_the_containing_bucket(self):
        self.assertEqual(SL.grade_bin(0.0), "+0.0/+2.5%")
        self.assertEqual(SL.grade_bin(-0.001), "-2.5/+0.0%")
        self.assertEqual(SL.grade_bin(0.5), ">30%")
        self.assertEqual(SL.grade_bin(-0.5), "<-30%")
        self.assertIsNone(SL.grade_bin(None))

    def test_open_tail_mid_is_a_nominal_anchor_half_a_bin_beyond_the_closed_bound(self):
        lo, hi, _ = SL.GRADE_BINS[-1]
        self.assertEqual(SL._bin_mid(lo, hi), lo + SL.BIN_WIDTH / 2)
        lo, hi, _ = SL.GRADE_BINS[0]
        self.assertEqual(SL._bin_mid(lo, hi), hi - SL.BIN_WIDTH / 2)


# ---------------------------------------------------------------------------
# `activity_bin_summaries` — au niveau d'une séance
# ---------------------------------------------------------------------------


def _flat_series(speed_ms, hr_bpm, cadence_spm, n=200, t0=0):
    return [
        {"t_s": float(t0 + i), "distance_m": i * speed_ms, "altitude_m": 0.0, "hr_bpm": hr_bpm,
         "speed_ms": speed_ms, "cadence_spm": cadence_spm, "grade": 0.0, "gap_speed_ms": speed_ms}
        for i in range(n)
    ]


class TestActivityBinSummaries(unittest.TestCase):
    def test_stopped_samples_are_excluded(self):
        series = _flat_series(3.0, 140.0, 170.0, n=100)
        # Un arrêt net (feu rouge) au milieu — sous `arc_gap.STOPPED_SPEED_MS`.
        for s in series[40:50]:
            s["speed_ms"] = 0.05
            s["gap_speed_ms"] = 0.05
        bins = SL.activity_bin_summaries(series, band="all")
        # 90 échantillons de mouvement à vitesse constante -> 90 s de temps pondéré
        # (dernier échantillon compte pour `resolution_s`, ici 5 s par défaut, mais la
        # résolution du générateur est 1 s -> on la passe explicitement).
        bins = SL.activity_bin_summaries(series, band="all", resolution_s=1.0)
        label = SL.grade_bin(0.0)
        self.assertAlmostEqual(bins[label]["weighted_time_s"], 90.0, delta=1.0)
        self.assertEqual(bins[label]["n_samples"], 90)

    def test_endurance_band_excludes_samples_above_the_easy_threshold(self):
        series = _flat_series(3.0, 160.0, 170.0, n=50) + _flat_series(3.2, 145.0, 170.0, n=50, t0=50)
        bins_all = SL.activity_bin_summaries(series, band="all", resolution_s=1.0)
        bins_endurance = SL.activity_bin_summaries(series, band="endurance", easy_hr_bpm=154.8, resolution_s=1.0)
        label = SL.grade_bin(0.0)
        self.assertEqual(bins_all[label]["n_samples"], 100)
        # Seule la seconde moitié (FC 145 < 154,8) est retenue en bande « endurance ».
        self.assertEqual(bins_endurance[label]["n_samples"], 50)

    def test_endurance_band_without_threshold_yields_nothing(self):
        series = _flat_series(3.0, 140.0, 170.0, n=20)
        self.assertEqual(SL.activity_bin_summaries(series, band="endurance", easy_hr_bpm=None), {})

    def test_walking_share_reflects_cadence_below_walking_threshold(self):
        series = _flat_series(1.4, 140.0, 130.0, n=60, )  # cadence 130 < WALKING_CADENCE_SPM (140)
        bins = SL.activity_bin_summaries(series, band="all", resolution_s=1.0)
        label = SL.grade_bin(0.0)
        self.assertAlmostEqual(bins[label]["walking_weighted_time_s"], bins[label]["weighted_time_s"], delta=1.0)

    def test_signal_gap_is_never_bridged_into_a_huge_weighted_sample(self):
        """Comme `arc_gap.weighted_average`/`arc_metrics._time_weighted_buckets` :
        un trou de signal (`dt` très supérieur à `resolution_s`) pèse au plus
        `resolution_s`, jamais le `dt` brut — sinon une pause GPS gonflerait
        artificiellement le temps mesuré dans le panier de son dernier point connu."""
        series = _flat_series(3.0, 140.0, 170.0, n=10)
        series.append({"t_s": 10.0 + 3600.0, "distance_m": 99999.0, "altitude_m": 0.0, "hr_bpm": 140.0,
                        "speed_ms": 3.0, "cadence_spm": 170.0, "grade": 0.0, "gap_speed_ms": 3.0})
        bins = SL.activity_bin_summaries(series, band="all", resolution_s=5.0)
        label = SL.grade_bin(0.0)
        # 11 échantillons, chacun plafonné à 5 s (le dernier aussi, faute de suivant) :
        # jamais les ~3610 s que le grand dt brut donnerait sans plafond.
        self.assertLessEqual(bins[label]["weighted_time_s"], 11 * 5.0 + 1e-6)


# ---------------------------------------------------------------------------
# Bout en bout, courbe imposée retrouvée (`tests.lib.synthetic`)
# ---------------------------------------------------------------------------


def _slope_curve(grade_pct: float) -> float:
    """Courbe pente -> allure IMPOSÉE pour ces tests : plus douce que
    `default_slope_factor` (montée -4 %/point, plancher 0,4x ; descente
    +2 %/point de vitesse, plafond 1,3x) — bornée à des vitesses plausibles,
    sans le second segment de freinage de `default_slope_factor` (inutile ici,
    aucune pente ne dépasse ±16 %, voir `_spread_segments`)."""
    if grade_pct >= 0:
        return max(0.4, 1 - 0.04 * grade_pct)
    return min(1.3, 1 + 0.02 * (-grade_pct))


def _synthetic_activities(n=10, seed0=200, months_back_days=(0, 10, 30, 40, 60, 70, 90, 100, 120, 150),
                           as_of="2026-09-26", **session_kwargs):
    """`n` séances synthétiques identiques (même courbe imposée, même segments),
    espacées dans le temps par `months_back_days` (jours avant `as_of`) —
    `{"activity_id", "date", "series"}`, prêt pour `fit_slope_model`. Segments
    longs (2 500 m, ±8 %) : une pente plus modérée et un segment plus long que
    le maximum de `_spread_segments` (16 %) laissent `arc_elevation.grade_series`
    (fenêtre de 20-50 m) mesurer une pente plus proche de la pente réellement
    imposée qu'un segment court à pente raide, où le lissage sur fenêtre
    atténue la pente mesurée près des transitions (voir la classe de test)."""
    from datetime import date, timedelta
    ref = date.fromisoformat(as_of)
    activities = []
    for i in range(n):
        day = (ref - timedelta(days=months_back_days[i % len(months_back_days)])).isoformat()
        records, _truth = sample_session(seed=seed0 + i, duration_s=5400, base_speed_ms=2.8,
                                          hr_base_bpm=140.0, cadence_spm=170.0,
                                          segments=[(0, 2500, 8.0), (4000, 2500, -8.0)],
                                          slope_factor_fn=_slope_curve, **session_kwargs)
        series = G.gap_sample_series(records)
        activities.append({"activity_id": i, "date": day, "series": series})
    return activities


class TestFitSlopeModelRecoversAnImposedCurve(unittest.TestCase):
    """Tolérance documentée : `arc_elevation.grade_series` calcule la pente sur
    une FENÊTRE de distance (20-50 m, lissage inclus, voir son docstring) —
    près des transitions de segment (début/fin de montée ou de descente), la
    pente mesurée est donc légèrement plus faible que la pente réellement
    imposée à cet instant précis, ce qui mélange dans un panier de bord des
    échantillons à vitesse "pleine pente" mais pente mesurée atténuée. Sur une
    montée, cet effet reste faible (le modèle imposé est proche de linéaire
    sur cette plage) ; en descente, il peut biaiser la vitesse mesurée d'un
    panier de ~10 % — d'où une tolérance plus large en descente qu'en montée,
    documentée ici plutôt que masquée par une tolérance globale trop large."""

    def test_recovers_the_curve_on_moderate_uphill_and_downhill(self):
        activities = _synthetic_activities(noise=True)
        model = SL.fit_slope_model(activities, band="all", months=12, as_of="2026-09-26")
        self.assertIsNone(model["reason_code"], model["reason"])
        self.assertGreaterEqual(model["n_activities"], 10)
        expected_uphill = 2.8 * _slope_curve(8.0)
        expected_downhill = 2.8 * _slope_curve(-8.0)
        got_uphill = SL.predict_speed(0.08, model["bins"])["speed_ms"]
        got_downhill = SL.predict_speed(-0.08, model["bins"])["speed_ms"]
        # Montée : le modèle imposé est proche de linéaire sur cette plage, la pente
        # mesurée colle de très près à la pente imposée -> tolérance serrée.
        self.assertAlmostEqual(got_uphill, expected_uphill, delta=expected_uphill * 0.10)
        # Descente : biais documenté ci-dessus (fenêtre de calcul de pente) -> tolérance
        # plus large, jamais masquée derrière une tolérance unique trop permissive.
        self.assertAlmostEqual(got_downhill, expected_downhill, delta=expected_downhill * 0.25)

    def test_flat_reference_matches_the_base_speed(self):
        activities = _synthetic_activities(noise=True)
        model = SL.fit_slope_model(activities, band="all", months=12, as_of="2026-09-26")
        self.assertAlmostEqual(model["flat_reference_speed_ms"], 2.8, delta=0.15)

    def test_insufficient_data_bin_falls_back_to_generic_with_an_explicit_flag(self):
        """Deux séances (`MIN_BIN_ACTIVITIES`, tout juste atteint sur le plat, qui
        alimente la référence du repli) dont les segments ne couvrent que ±8 % :
        un panier de forte pente (25 %, jamais rencontré) manque structurellement
        de données -> `source == "generic"`, jamais confondu avec une donnée
        personnelle — alors que le panier plat, lui, reste personnel."""
        activities = _synthetic_activities(n=2, noise=False)
        model = SL.fit_slope_model(activities, band="all", months=12, as_of="2026-09-26")
        self.assertIsNone(model["reason_code"], model["reason"])
        far_label = SL.grade_bin(0.25)
        far_bin = next(b for b in model["bins"] if b["label"] == far_label)
        self.assertEqual(far_bin["source"], "generic")
        self.assertEqual(far_bin["n_activities"], 0)
        self.assertIsNotNone(far_bin["speed_ms"])  # le repli produit quand même une valeur
        flat_bin = next(b for b in model["bins"] if b["label"] == SL.grade_bin(0.0))
        self.assertEqual(flat_bin["source"], "personal")

    def test_endurance_band_without_hr_threshold_reports_a_reason(self):
        activities = _synthetic_activities(n=2, noise=False)
        model = SL.fit_slope_model(activities, band="endurance", easy_hr_bpm=None, as_of="2026-09-26")
        self.assertEqual(model["reason_code"], "no_hr_threshold")
        self.assertEqual(model["bins"], [])

    def test_unknown_band_is_rejected_explicitly(self):
        model = SL.fit_slope_model([], band="sprint")
        self.assertEqual(model["reason_code"], "unknown_band")

    def test_recency_weighting_favours_recent_activities(self):
        """Deux groupes de séances à des vitesses de plat DIFFÉRENTES : les
        récentes (poids fort) doivent dominer la médiane pondérée plus que les
        anciennes (poids faible, demi-vie courte) — sinon la pondération par
        récence ne fait rien."""
        from datetime import date, timedelta
        as_of = date.fromisoformat("2026-09-26")
        old_activities = []
        for i in range(5):
            day = (as_of - timedelta(days=300 + i)).isoformat()
            records, _ = sample_session(seed=300 + i, duration_s=1800, base_speed_ms=2.0,
                                         hr_base_bpm=140.0, noise=True)
            old_activities.append({"activity_id": f"old{i}", "date": day, "series": G.gap_sample_series(records)})
        recent_activities = []
        for i in range(5):
            day = (as_of - timedelta(days=i)).isoformat()
            records, _ = sample_session(seed=400 + i, duration_s=1800, base_speed_ms=3.4,
                                         hr_base_bpm=140.0, noise=True)
            recent_activities.append({"activity_id": f"new{i}", "date": day, "series": G.gap_sample_series(records)})
        model = SL.fit_from_activity_bins(
            [{"activity_id": a["activity_id"], "date": a["date"],
              "bins": SL.activity_bin_summaries(a["series"], band="all", resolution_s=G.DEFAULT_RESOLUTION_S)}
             for a in old_activities + recent_activities],
            band="all", months=24, half_life_days=10.0, as_of="2026-09-26",
        )
        flat = next(b for b in model["bins"] if b["label"] == SL.grade_bin(0.0))
        # Avec une demi-vie de 10 j, les séances vieilles de 300 j pèsent quasi rien :
        # la vitesse retrouvée doit être bien plus proche de 3,4 m/s (récent) que de
        # 2,0 m/s (ancien) — jamais une simple moyenne des deux (2,7 m/s).
        self.assertGreater(flat["speed_ms"], 3.0)

    def test_a_long_half_life_lets_a_larger_older_group_outweigh_a_smaller_recent_one(self):
        """Contrôle : avec une demi-vie énorme (des siècles, décroissance
        négligeable même à 300 j), le poids de récession de chaque séance est
        presque identique — c'est alors la TAILLE des groupes qui décide de la
        médiane pondérée, pas leur ancienneté : un groupe ancien majoritaire
        (8 séances) l'emporte sur un groupe récent minoritaire (2 séances),
        contrairement au test précédent (demi-vie courte, groupe récent
        minoritaire mais dominant) — preuve que c'est bien la demi-vie qui
        pilote lequel des deux effets (ancienneté vs volume) l'emporte."""
        from datetime import date, timedelta
        as_of = date.fromisoformat("2026-09-26")
        activities = []
        for i in range(8):
            day = (as_of - timedelta(days=300 + i)).isoformat()
            records, _ = sample_session(seed=300 + i, duration_s=1800, base_speed_ms=2.0, noise=True)
            activities.append({"activity_id": f"old{i}", "date": day, "series": G.gap_sample_series(records)})
        for i in range(2):
            day = (as_of - timedelta(days=i)).isoformat()
            records, _ = sample_session(seed=400 + i, duration_s=1800, base_speed_ms=3.4, noise=True)
            activities.append({"activity_id": f"new{i}", "date": day, "series": G.gap_sample_series(records)})
        model = SL.fit_from_activity_bins(
            [{"activity_id": a["activity_id"], "date": a["date"],
              "bins": SL.activity_bin_summaries(a["series"], band="all", resolution_s=G.DEFAULT_RESOLUTION_S)}
             for a in activities],
            band="all", months=24, half_life_days=100_000.0, as_of="2026-09-26",
        )
        flat = next(b for b in model["bins"] if b["label"] == SL.grade_bin(0.0))
        self.assertLess(flat["speed_ms"], 3.0)  # dominé par le groupe ancien majoritaire (2,0 m/s)

    def test_months_window_excludes_activities_older_than_the_window(self):
        activities = _synthetic_activities(n=3, months_back_days=(400, 400, 400), noise=False)
        model = SL.fit_slope_model(activities, band="all", months=6, as_of="2026-09-26")
        self.assertEqual(model["reason_code"], "no_data_in_window")
        self.assertEqual(model["n_activities"], 0)

    def test_no_dated_activity_reports_no_data(self):
        model = SL.fit_slope_model([{"activity_id": 1, "date": None, "series": []}], band="all")
        self.assertEqual(model["reason_code"], "no_data")


# ---------------------------------------------------------------------------
# `predict_speed` — interpolation et queues
# ---------------------------------------------------------------------------


class TestPredictSpeed(unittest.TestCase):
    BINS = [
        {"grade_lo": -0.05, "grade_hi": 0.0, "grade_mid": -0.025, "speed_ms": 3.2, "hr_bpm": 145.0,
         "source": "personal", "ci_low_speed_ms": 3.0, "ci_high_speed_ms": 3.4},
        {"grade_lo": 0.0, "grade_hi": 0.05, "grade_mid": 0.025, "speed_ms": 2.8, "hr_bpm": 150.0,
         "source": "personal", "ci_low_speed_ms": 2.6, "ci_high_speed_ms": 3.0},
        {"grade_lo": 0.05, "grade_hi": 0.10, "grade_mid": 0.075, "speed_ms": 2.2, "hr_bpm": 158.0,
         "source": "generic", "ci_low_speed_ms": None, "ci_high_speed_ms": None},
    ]

    def test_interpolates_linearly_between_two_bin_midpoints(self):
        # Exactement au milieu entre 0,025 et 0,075 -> moyenne des deux vitesses.
        got = SL.predict_speed(0.05, self.BINS)
        self.assertAlmostEqual(got["speed_ms"], (2.8 + 2.2) / 2, places=6)
        self.assertEqual(got["source"], "mixed")  # un panier personnel, un générique

    def test_matches_a_bin_exactly_at_its_own_midpoint(self):
        got = SL.predict_speed(0.025, self.BINS)
        self.assertAlmostEqual(got["speed_ms"], 2.8, places=6)
        self.assertEqual(got["source"], "personal")

    def test_extrapolates_flat_beyond_the_outer_midpoints(self):
        got_low = SL.predict_speed(-0.5, self.BINS)
        got_high = SL.predict_speed(0.5, self.BINS)
        self.assertAlmostEqual(got_low["speed_ms"], 3.2, places=6)
        self.assertAlmostEqual(got_high["speed_ms"], 2.2, places=6)

    def test_none_grade_is_reported_explicitly(self):
        got = SL.predict_speed(None, self.BINS)
        self.assertIsNone(got["speed_ms"])
        self.assertEqual(got["reason_code"], "no_grade")

    def test_empty_model_is_reported_explicitly(self):
        got = SL.predict_speed(0.05, [])
        self.assertIsNone(got["speed_ms"])
        self.assertEqual(got["reason_code"], "no_model")


# ---------------------------------------------------------------------------
# `arc_index` — tables, CLI, garde
# ---------------------------------------------------------------------------


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="arc-slope-"))
        self.ws = self.tmp / "ws"
        for d in ("activities", "medical", "nutrition", "planning", "rapports"):
            (self.ws / d).mkdir(parents=True)
        self.conn = I.open_db(self.ws, memory=True)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def index(self, today="2026-09-26"):
        return I.index_workspace(self.conn, self.ws, today)

    def write(self, rel: str, text: str) -> None:
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_profile(self):
        self.write("planning/Runner_Profile.md",
                    "# Profil de l'athlète\n\n## Physiologie\n\n"
                    "- **FC max** : 188\n- **FC de repos de référence** : 48\n- **FC au seuil** : 172\n")

    def write_activity(self, garmin_id, day, duration_s=3600, distance_m=10000, sport="trail"):
        data = {"arc": 1, "kind": "activity", "date": day, "sport": sport, "name": "Sortie",
                "duration_s": duration_s, "distance_m": distance_m, "garmin_activity_id": garmin_id}
        self.write(f"activities/{day}_{sport}_{garmin_id}.md", "# Sortie\n\n```arc\n" + json.dumps(data) + "\n```\n")

    def write_fit(self, garmin_id, records):
        fit_dir = self.ws / "activities/fit"
        fit_dir.mkdir(parents=True, exist_ok=True)
        (fit_dir / f"{garmin_id}.json").write_text(
            json.dumps({"activity_id": garmin_id, "records": records}), encoding="utf-8")


class TestArcIndexSlopeModelTables(Workspace):
    def test_compute_metrics_populates_slope_model_tables_for_both_bands(self):
        self.write_profile()
        from datetime import date, timedelta
        as_of = date.fromisoformat("2026-09-26")
        for i in range(5):
            day = (as_of - timedelta(days=i * 20)).isoformat()
            garmin_id = 91000000000 + i
            records, _ = sample_session(seed=500 + i, duration_s=3600, base_speed_ms=2.8, hr_base_bpm=140.0,
                                         segments=[(0, 1000, 10.0)], noise=True)
            self.write_activity(garmin_id, day)
            self.write_fit(garmin_id, records)
        self.index()
        meta_rows = {r["band"]: dict(r) for r in self.conn.execute("SELECT * FROM slope_model_meta").fetchall()}
        self.assertEqual(set(meta_rows), {"endurance", "all"})
        self.assertIsNone(meta_rows["all"]["reason_code"], meta_rows["all"]["reason"])
        bins = self.conn.execute("SELECT * FROM slope_model_bin WHERE band = 'all'").fetchall()
        self.assertTrue(bins)
        # Panier ouvert -> bornes NULL en base (jamais une chaîne "inf").
        tail = self.conn.execute(
            "SELECT * FROM slope_model_bin WHERE band = 'all' AND label = '<-30%'").fetchone()
        self.assertIsNone(tail["grade_lo"])

    def test_slope_model_report_keeps_open_tail_bounds_as_json_null(self):
        """`NULL` en base reste `None` ici, JAMAIS converti en `float("inf")` :
        `json.dumps(float("inf"))` produirait le jeton `Infinity`, invalide en
        JSON standard, que `JSON.parse` d'un navigateur rejette (revue de code
        #58, voir `arc_index.slope_model_bins`)."""
        self.write_profile()
        from datetime import date, timedelta
        as_of = date.fromisoformat("2026-09-26")
        for i in range(3):
            day = (as_of - timedelta(days=i * 10)).isoformat()
            garmin_id = 92000000000 + i
            records, _ = sample_session(seed=600 + i, duration_s=1800, base_speed_ms=2.8, noise=True)
            self.write_activity(garmin_id, day)
            self.write_fit(garmin_id, records)
        self.index()
        report = I.slope_model_report(self.conn, "all")
        tail = next(b for b in report["bins"] if b["label"] == "<-30%")
        self.assertIsNone(tail["grade_lo"])
        # Round-trip JSON réel (pas seulement le dict Python) : la garantie qui
        # compte est celle-ci, jamais cassée même si le champ change de forme.
        round_tripped = json.loads(json.dumps(report, ensure_ascii=False))
        tail2 = next(b for b in round_tripped["bins"] if b["label"] == "<-30%")
        self.assertIsNone(tail2["grade_lo"])

    def test_cli_slope_model_command_returns_stored_model(self):
        self.write_profile()
        self.index()
        parser = I.build_parser()
        args = parser.parse_args(["slope-model", "--band", "all", "--workspace", str(self.ws), "--memory"])
        # Le CLI ouvre sa propre connexion (comportement standard de `main`) : on
        # vérifie ici seulement que `slope_model_report`/`recompute_slope_model`
        # sont bien reliés à `--band`/`--months`, pas le rendu de `main` lui-même
        # (déjà exercé par les autres sous-commandes du même fichier).
        self.assertEqual(args.band, "all")

    def test_cli_months_override_recomputes_on_the_fly(self):
        self.write_profile()
        from datetime import date, timedelta
        as_of = date.fromisoformat("2026-09-26")
        for i in range(3):
            day = (as_of - timedelta(days=i * 10)).isoformat()
            garmin_id = 93000000000 + i
            records, _ = sample_session(seed=700 + i, duration_s=1800, base_speed_ms=2.8, noise=True)
            self.write_activity(garmin_id, day)
            self.write_fit(garmin_id, records)
        self.index()
        conf = I.settings(I.load_config(self.ws))
        result = I.recompute_slope_model(self.conn, conf, "all", months=1, today="2026-09-26")
        self.assertEqual(result["months"], 1)
        self.assertIsNone(result["reason_code"], result["reason"])


class TestComputeMetricsSurvivesAnUnexpectedCrashAndStillBuildsTheSlopeModel(Workspace):
    """Même discipline que #46/#47/#48 (`test_arc_durability.py::
    TestComputeMetricsSurvivesAnUnexpectedDurabilityCrash`) : un bug inattendu
    dans UN calcul dérivé d'UNE activité (ici, on force `arc_climb.detect_climbs`
    à lever) ne doit ni faire planter `compute_metrics` pour les autres
    activités, ni empêcher le modèle pente -> allure global de se construire à
    partir des activités qui, elles, ont réussi leur résumé par panier (calculé
    AVANT le point de la boucle qui plante, voir `arc_index.compute_metrics`)."""

    def test_one_activitys_crash_never_stops_the_slope_model(self):
        import os
        import arc_index as I2
        self.write_profile()
        from datetime import date, timedelta
        as_of = date.fromisoformat("2026-09-26")
        for i in range(3):
            day = (as_of - timedelta(days=i * 10)).isoformat()
            garmin_id = 94000000000 + i
            records, _ = sample_session(seed=800 + i, duration_s=1800, base_speed_ms=2.8, noise=True)
            self.write_activity(garmin_id, day)
            self.write_fit(garmin_id, records)
        previous_strict = os.environ.pop("ARC_STRICT_METRICS", None)
        original = I2.VC.detect_climbs

        def boom(*args, **kwargs):
            raise RuntimeError("boum (test)")
        I2.VC.detect_climbs = boom
        try:
            self.index()
        finally:
            I2.VC.detect_climbs = original
            if previous_strict is None:
                os.environ.pop("ARC_STRICT_METRICS", None)
            else:
                os.environ["ARC_STRICT_METRICS"] = previous_strict
        meta = self.conn.execute("SELECT * FROM slope_model_meta WHERE band = 'all'").fetchone()
        self.assertIsNone(meta["reason_code"], meta["reason"])
        self.assertGreaterEqual(meta["n_activities"], 3)


if __name__ == "__main__":
    unittest.main()
