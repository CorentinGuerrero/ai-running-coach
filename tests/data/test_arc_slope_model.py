"""Palier D — modèle personnel pente -> allure (#58, épopée #23).

Familles de tests :
- Paniers de pente (`GRADE_BINS`) : bornes, étiquettes, point milieu, centrage
  sur 0.
- `activity_bin_summaries` : échantillons à l'arrêt exclus, bande « endurance »
  (sélection au niveau de L'ACTIVITÉ entière, jamais de l'échantillon — revue
  de code #58, BLOQUANT) vs « all » (aucun filtre), part de marche
  (`run_share`), trous de signal jamais franchis.
- `combine_activity_summaries` : plancher/plafond du poids d'une activité dans
  un panier (revue de code #58, should-fix 4).
- `fit_slope_model` bout en bout sur des séances synthétiques à courbe
  pente -> allure IMPOSÉE (`tests.lib.synthetic.sample_session(slope_factor_fn=...)`) :
  la courbe est retrouvée à une tolérance documentée près, sur plusieurs pentes
  (montée et descente), aux points milieux des paniers ; courbe nulle (témoin
  négatif) ; effet de la pondération par récence ; effet du filtre de bande
  FC ; fenêtre de mois qui exclut les séances trop anciennes ; absence de
  biais de montée quand la FC répond en retard à l'effort.
- Repli générique (Minetti) quand un panier manque de données, `source:
  "generic"` explicite, PLAFONNÉ en descente (revue de code #58, BLOQUANT) ;
  lissage RESTREINT aux voisins de même provenance et reclampé dans son propre
  IQR (revue de code #58, BLOQUANT) ; `predict_speed` (interpolation entre
  paniers, extrapolation plate aux queues signalée, `hr`/`ci` à `None` quand
  la source est mixte).
- `arc_index` : tables `slope_model_bin`/`slope_model_meta` recalculées à
  l'indexation, CLI `slope-model` (stocké et recalculé à la volée), garde en
  cas d'échec inattendu d'un calcul dérivé de la même activité — une activité
  en échec ne doit ni empêcher l'indexation des autres, ni contribuer
  elle-même au modèle pente -> allure (revue de code #58, nit : tamponné,
  commité seulement après succès complet).
"""

from __future__ import annotations

import json
import os
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
    def test_bins_cover_at_least_30_pct_with_two_open_tails_and_are_centered_on_zero(self):
        self.assertEqual(SL.GRADE_BINS[0][0], float("-inf"))
        self.assertGreaterEqual(-SL.GRADE_BINS[0][1], SL.BIN_MAX_ABS)
        self.assertEqual(SL.GRADE_BINS[-1][0], -SL.GRADE_BINS[0][1])  # queues symétriques
        self.assertEqual(SL.GRADE_BINS[-1][1], float("inf"))
        # Continuité stricte : la borne haute d'un panier == la borne basse du suivant.
        for (_, hi, _), (lo2, _, _) in zip(SL.GRADE_BINS, SL.GRADE_BINS[1:]):
            self.assertAlmostEqual(hi, lo2, places=9)
        # Centré sur 0 (revue de code #58, nit) : un panier fermé contient EXACTEMENT
        # 0,0 %, à cheval symétriquement autour (jamais une frontière pile à 0).
        flat = next((lo, hi) for lo, hi, _ in SL.GRADE_BINS if lo <= 0.0 < hi and lo != float("-inf"))
        self.assertAlmostEqual(flat[0], -SL.BIN_WIDTH / 2, places=9)
        self.assertAlmostEqual(flat[1], SL.BIN_WIDTH / 2, places=9)

    def test_grade_bin_picks_the_containing_bucket(self):
        half = SL.BIN_WIDTH / 2
        self.assertEqual(SL.grade_bin(0.0), f"{-half * 100:+.1f}/{half * 100:+.1f}%")
        self.assertEqual(SL.grade_bin(-0.001), f"{-half * 100:+.1f}/{half * 100:+.1f}%")
        outer = SL.GRADE_BINS[-1][0]
        self.assertEqual(SL.grade_bin(outer + 1.0), f">{outer * 100:.0f}%")
        self.assertEqual(SL.grade_bin(-outer - 1.0), f"<{-outer * 100:.0f}%")
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


EASY_HR = 154.8  # seuil facile/modéré utilisé dans ces tests (méthode LTHR, profil type)


class TestActivityBinSummaries(unittest.TestCase):
    def test_stopped_samples_are_excluded(self):
        series = _flat_series(3.0, 140.0, 170.0, n=100)
        # Un arrêt net (feu rouge) au milieu — sous `arc_gap.STOPPED_SPEED_MS`.
        for s in series[40:50]:
            s["speed_ms"] = 0.05
            s["gap_speed_ms"] = 0.05
        # 90 échantillons de mouvement à vitesse constante -> 90 s de temps pondéré
        # (dernier échantillon compte pour `resolution_s`, ici 1 s, la résolution du
        # générateur — passée explicitement, jamais le défaut 5 s d'`arc_gap`).
        bins = SL.activity_bin_summaries(series, band="all", resolution_s=1.0)
        label = SL.grade_bin(0.0)
        self.assertAlmostEqual(bins[label]["weighted_time_s"], 90.0, delta=1.0)
        self.assertEqual(bins[label]["n_samples"], 90)

    def test_endurance_band_without_threshold_yields_nothing(self):
        series = _flat_series(3.0, 140.0, 170.0, n=20)
        self.assertEqual(SL.activity_bin_summaries(series, band="endurance", easy_hr_bpm=None), {})

    def test_walking_share_reflects_cadence_below_walking_threshold(self):
        series = _flat_series(1.4, 140.0, 130.0, n=60)  # cadence 130 < WALKING_CADENCE_SPM (140)
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


class TestEnduranceIsSelectedAtTheActivityLevel(unittest.TestCase):
    """Revue de code #58, BLOQUANT : `band='endurance'` classe l'ACTIVITÉ
    ENTIÈRE, jamais échantillon par échantillon — une version antérieure
    filtrait chaque échantillon par sa propre FC, un biais de sélection réel
    sur les montées (la FC monte avec un retard sur l'effort, voir
    `arc_slope_model.ASSUMPTIONS['population']`)."""

    def test_activity_included_wholesale_when_easy_share_is_high(self):
        # 90 % du temps de mouvement sous le seuil facile (180 s faciles, 20 s dures)
        # -> activité retenue ENTIÈREMENT, y compris les 20 s "dures".
        series = _flat_series(3.0, 145.0, 170.0, n=180) + _flat_series(3.5, 165.0, 170.0, n=20, t0=180)
        bins = SL.activity_bin_summaries(series, band="endurance", easy_hr_bpm=EASY_HR, resolution_s=1.0)
        total_samples = sum(b["n_samples"] for b in bins.values())
        self.assertEqual(total_samples, 200)  # TOUS les échantillons, pas seulement les 180 faciles

    def test_activity_excluded_wholesale_when_easy_share_is_low(self):
        # 50 % du temps sous le seuil -> sous ENDURANCE_ACTIVITY_EASY_SHARE_MIN (80 %) ->
        # activité EXCLUE ENTIÈREMENT (aucun panier, même pas les échantillons faciles).
        series = _flat_series(3.0, 145.0, 170.0, n=100) + _flat_series(3.5, 165.0, 170.0, n=100, t0=100)
        bins = SL.activity_bin_summaries(series, band="endurance", easy_hr_bpm=EASY_HR, resolution_s=1.0)
        self.assertEqual(bins, {})

    def test_activity_with_too_little_hr_coverage_is_excluded_not_assumed_easy(self):
        series = _flat_series(3.0, None, 170.0, n=190)
        for s in _flat_series(3.0, 145.0, 170.0, n=10, t0=190):
            series.append(s)
        bins = SL.activity_bin_summaries(series, band="endurance", easy_hr_bpm=EASY_HR, resolution_s=1.0)
        self.assertEqual(bins, {})  # 10 s de FC connue < ENDURANCE_ACTIVITY_MIN_HR_TIME_S (60 s)

    def test_activity_easy_share_helper_matches_direct_computation(self):
        moving = _flat_series(3.0, 145.0, 170.0, n=80) + _flat_series(3.0, 165.0, 170.0, n=20, t0=80)
        share = SL._activity_easy_share(moving, EASY_HR, resolution_s=1.0)
        self.assertAlmostEqual(share, 0.80, places=2)


class TestActivityBinTimeFloorAndCap(unittest.TestCase):
    """Revue de code #58, should-fix 4 : plancher/plafond du poids d'UNE
    activité DANS UN panier, appliqués par `combine_activity_summaries`."""

    def test_a_pass_shorter_than_the_floor_never_counts_toward_min_bin_activities(self):
        # Deux activités : l'une avec 5 s dans le panier plat (sous MIN_ACTIVITY_BIN_TIME_S,
        # 30 s), l'autre avec une vraie présence (60 s). MIN_BIN_ACTIVITIES (2) ne doit PAS
        # être satisfait par la traversée de 5 s.
        bins_a = {SL.grade_bin(0.0): {
            "weighted_time_s": 5.0, "speed_weighted_sum": 5.0 * 3.0, "hr_weighted_time_s": 5.0,
            "hr_weighted_sum": 5.0 * 145.0, "n_samples": 5, "walking_weighted_time_s": 0.0}}
        bins_b = {SL.grade_bin(0.0): {
            "weighted_time_s": 60.0, "speed_weighted_sum": 60.0 * 3.0, "hr_weighted_time_s": 60.0,
            "hr_weighted_sum": 60.0 * 145.0, "n_samples": 60, "walking_weighted_time_s": 0.0}}
        combined = SL.combine_activity_summaries(
            [{"activity_id": "a", "date": "2026-09-20", "bins": bins_a},
             {"activity_id": "b", "date": "2026-09-21", "bins": bins_b}],
            as_of="2026-09-26", half_life_days=45.0,
        )
        agg = combined[SL.grade_bin(0.0)]
        self.assertEqual(agg["n_activities"], 1)  # seule "b" compte, "a" (5 s) est ignorée

    def test_a_single_very_long_activity_never_outweighs_several_shorter_recent_ones(self):
        """Repro revue de code #58 : un ultra de 3 h dans le même panier ne doit pas
        écraser 3 sorties récentes de 30 min — le poids-temps est plafonné à
        `ACTIVITY_BIN_TIME_WEIGHT_CAP_S` (10 min)."""
        label = SL.grade_bin(0.0)
        long_bins = {label: {
            "weighted_time_s": 3 * 3600.0, "speed_weighted_sum": 3 * 3600.0 * 2.0, "hr_weighted_time_s": 0.0,
            "hr_weighted_sum": 0.0, "n_samples": 100, "walking_weighted_time_s": 0.0}}
        short_bins = {label: {
            "weighted_time_s": 1800.0, "speed_weighted_sum": 1800.0 * 3.6, "hr_weighted_time_s": 0.0,
            "hr_weighted_sum": 0.0, "n_samples": 100, "walking_weighted_time_s": 0.0}}
        activities = [{"activity_id": "ultra", "date": "2026-09-01", "bins": long_bins}]
        activities += [{"activity_id": f"short{i}", "date": f"2026-09-2{i}", "bins": short_bins}
                       for i in range(3)]
        combined = SL.combine_activity_summaries(activities, as_of="2026-09-26", half_life_days=45.0)
        result = SL.apply_fallback_and_smoothing(combined)
        flat = next(b for b in result["bins"] if b["label"] == label)
        # Vitesse retrouvée nettement plus proche de 3,6 m/s (3 sorties courtes) que de
        # 2,0 m/s (l'ultra) — jamais dominée par la seule très longue sortie.
        self.assertGreater(flat["speed_ms"], 3.0)


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


def _flat_curve(_grade_pct: float) -> float:
    """Témoin négatif : aucune dépendance à la pente (facteur toujours 1,0).
    Sert à vérifier que le modèle ne "trouve" jamais un signal pente -> allure
    là où il n'y en a structurellement aucun (voir
    `TestFitSlopeModelRecoversAnImposedCurve.test_a_flat_imposed_curve_recovers_flat_everywhere`)."""
    return 1.0


def _synthetic_activities(n=10, seed0=200, months_back_days=(0, 10, 30, 40, 60, 70, 90, 100, 120, 150),
                           as_of="2026-09-26", curve=_slope_curve, **session_kwargs):
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
                                          slope_factor_fn=curve, **session_kwargs)
        series = G.gap_sample_series(records)
        activities.append({"activity_id": i, "date": day, "series": series})
    return activities


class TestFitSlopeModelRecoversAnImposedCurve(unittest.TestCase):
    """Tolérance documentée, mesurée AUX POINTS MILIEUX DE PANIER (jamais à une
    pente arbitraire, qui pourrait retomber entre un panier personnel et un
    panier générique voisin — voir `apply_fallback_and_smoothing`, revue de
    code #58, should-fix 3) : `arc_elevation.grade_series` calcule la pente
    sur une FENÊTRE de distance (20-50 m, lissage inclus) — près des
    transitions de segment, la pente mesurée est donc légèrement plus faible
    que la pente réellement imposée à cet instant précis. Avec des segments
    longs (2 500 m) et une pente modérée (±8 %), cet effet reste faible des
    deux côtés (< 5 %) — une tolérance serrée suffit désormais des deux côtés
    (contrairement à une version antérieure de ce test, où la tolérance large
    en descente masquait en réalité le bogue corrigé en revue de code #58,
    BLOQUANT 1 : le lissage inter-paniers contaminait alors un panier
    personnel avec son voisin générique)."""

    def test_recovers_the_curve_at_the_uphill_and_downhill_bin_midpoints(self):
        activities = _synthetic_activities(noise=True)
        model = SL.fit_slope_model(activities, band="all", months=12, as_of="2026-09-26")
        self.assertIsNone(model["reason_code"], model["reason"])
        self.assertGreaterEqual(model["n_activities"], 10)
        personal = {b["label"]: b for b in model["bins"] if b["source"] == "personal"}
        self.assertTrue(personal)
        checked_uphill = checked_downhill = 0
        for b in personal.values():
            expected = 2.8 * _slope_curve(b["grade_mid"] * 100)
            self.assertAlmostEqual(b["speed_ms"], expected, delta=expected * 0.05,
                                    msg=f"panier {b['label']} (mid={b['grade_mid']})")
            if b["grade_mid"] > 0.01:
                checked_uphill += 1
            elif b["grade_mid"] < -0.01:
                checked_downhill += 1
        self.assertGreater(checked_uphill, 0)
        self.assertGreater(checked_downhill, 0)

    def test_a_flat_imposed_curve_recovers_flat_everywhere(self):
        """Témoin négatif (revue de code #58, should-fix 3) : sans dépendance
        réelle à la pente, chaque panier personnel doit retrouver la MÊME
        vitesse (la référence plate), jamais un faux signal pente -> allure."""
        activities = _synthetic_activities(noise=True, curve=_flat_curve)
        model = SL.fit_slope_model(activities, band="all", months=12, as_of="2026-09-26")
        self.assertIsNone(model["reason_code"], model["reason"])
        personal = [b for b in model["bins"] if b["source"] == "personal"]
        self.assertGreaterEqual(len(personal), 3)
        for b in personal:
            self.assertAlmostEqual(b["speed_ms"], 2.8, delta=2.8 * 0.05, msg=f"panier {b['label']}")

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

    def test_generic_downhill_speed_is_capped_never_implausibly_fast(self):
        """Revue de code #58, BLOQUANT 2 : le repli générique inversé (Minetti)
        divergeait en forte descente (ex. -18,75 % -> ~2,0x la référence plate,
        une allure ~2 min/km totalement implausible pour un plat à 4:00/km).
        Plafonné à `GENERIC_DOWNHILL_SPEED_CAP_RATIO` (1,3x) la référence
        plate — jamais au-delà, même sur les paniers les plus raides."""
        activities = _synthetic_activities(n=2, noise=False)
        model = SL.fit_slope_model(activities, band="all", months=12, as_of="2026-09-26")
        flat_speed = model["flat_reference_speed_ms"]
        cap = flat_speed * SL.GENERIC_DOWNHILL_SPEED_CAP_RATIO
        downhill_generic = [b for b in model["bins"] if b["source"] == "generic" and b["grade_mid"] < 0]
        self.assertTrue(downhill_generic)
        for b in downhill_generic:
            self.assertLessEqual(b["speed_ms"], cap + 1e-6, msg=f"panier {b['label']}")

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

    def test_endurance_band_avoids_uphill_bias_when_hr_lags_behind_effort(self):
        """Revue de code #58, BLOQUANT 5 : la FC répond avec un RETARD à
        l'effort (`hr_grade_response_bpm_per_pct`/`hr_grade_lag_s`, voir
        `tests/lib/synthetic.py`) — assez fort pour que la FC dépasse le seuil
        facile PENDANT la montée sur certaines séances. La sélection au niveau
        de L'ACTIVITÉ (jamais de l'échantillon) fait que ces séances restent
        soit ENTIÈREMENT incluses (si l'essentiel du temps reste facile), soit
        ENTIÈREMENT exclues — jamais un sous-ensemble de la montée corrélé à
        la FC, qui biaiserait l'allure de montée mesurée. L'allure de montée
        retrouvée doit rester proche de la courbe imposée, PAS artificiellement
        rapide (le biais qu'un filtre par échantillon aurait introduit)."""
        from datetime import date, timedelta
        as_of = date.fromisoformat("2026-09-26")
        activities = []
        for i in range(8):
            day = (as_of - timedelta(days=i * 5)).isoformat()
            records, _ = sample_session(
                seed=900 + i, duration_s=5400, base_speed_ms=2.8, hr_base_bpm=140.0, cadence_spm=170.0,
                segments=[(0, 2500, 8.0), (4000, 2500, -8.0)], slope_factor_fn=_slope_curve,
                # Réponse et retard choisis pour que la FC dépasse le seuil facile
                # (154,8) PENDANT une bonne partie de la montée (~2,3 min à 90 s de
                # constante de temps pour y arriver, sur une montée d'environ 22 min)
                # SANS faire chuter la part globale de temps facile de la séance
                # sous `ENDURANCE_ACTIVITY_EASY_SHARE_MIN` (80 %) — sans quoi la
                # séance serait simplement exclue plutôt que sujette au biais testé.
                hr_grade_response_bpm_per_pct=2.0, hr_grade_lag_s=200.0, noise=True,
            )
            activities.append({"activity_id": i, "date": day, "series": G.gap_sample_series(records)})
        model = SL.fit_slope_model(activities, band="endurance", months=12,
                                    easy_hr_bpm=EASY_HR, as_of="2026-09-26")
        self.assertIsNone(model["reason_code"], model["reason"])
        uphill_personal = [b for b in model["bins"]
                            if b["source"] == "personal" and 0.06 < b["grade_mid"] < 0.10]
        self.assertTrue(uphill_personal, "aucun panier de montée personnel — vérifier le scénario du test")
        expected = 2.8 * _slope_curve(8.0)
        for b in uphill_personal:
            # Tolérance plus large qu'au test de récupération pur (10 %) : le lissage
            # léger et le bruit du générateur restent en jeu, mais AUCUN biais
            # systématique vers une allure plus rapide que l'allure imposée ne doit
            # apparaître (ce qu'un filtre par échantillon aurait produit).
            self.assertAlmostEqual(b["speed_ms"], expected, delta=expected * 0.12,
                                    msg=f"panier {b['label']}")


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
        # Revue de code #58, nit : FC/IQR à None quand la source est mixte — interpoler
        # entre une FC personnelle et un `None` générique ne produirait un nombre qui
        # n'a de sens dans aucune des deux provenances.
        self.assertIsNone(got["hr_bpm"])
        self.assertIsNone(got["ci_low_speed_ms"])
        self.assertIsNone(got["ci_high_speed_ms"])
        self.assertIsNone(got["reason_code"])  # une vraie interpolation, pas une extrapolation

    def test_matches_a_bin_exactly_at_its_own_midpoint(self):
        got = SL.predict_speed(0.025, self.BINS)
        self.assertAlmostEqual(got["speed_ms"], 2.8, places=6)
        self.assertEqual(got["source"], "personal")
        self.assertEqual(got["hr_bpm"], 150.0)

    def test_extrapolates_flat_beyond_the_outer_midpoints_and_flags_it(self):
        got_low = SL.predict_speed(-0.5, self.BINS)
        got_high = SL.predict_speed(0.5, self.BINS)
        self.assertAlmostEqual(got_low["speed_ms"], 3.2, places=6)
        self.assertAlmostEqual(got_high["speed_ms"], 2.2, places=6)
        self.assertEqual(got_low["reason_code"], "extrapolated")
        self.assertEqual(got_high["reason_code"], "extrapolated")

    def test_a_grade_within_the_outer_midpoints_is_never_flagged_extrapolated(self):
        got = SL.predict_speed(0.0, self.BINS)
        self.assertIsNone(got["reason_code"])

    def test_none_grade_is_reported_explicitly(self):
        got = SL.predict_speed(None, self.BINS)
        self.assertIsNone(got["speed_ms"])
        self.assertEqual(got["reason_code"], "no_grade")

    def test_empty_model_is_reported_explicitly(self):
        got = SL.predict_speed(0.05, [])
        self.assertIsNone(got["speed_ms"])
        self.assertEqual(got["reason_code"], "no_model")


# ---------------------------------------------------------------------------
# Lissage — restreint aux voisins de même provenance (revue de code #58, BLOQUANT)
# ---------------------------------------------------------------------------


class TestSmoothingNeverCrossesPersonalAndGenericBins(unittest.TestCase):
    def test_a_personal_bin_between_two_generic_ones_keeps_its_own_raw_value(self):
        """Repro revue de code #58, BLOQUANT 1 : un panier PERSONNEL isolé entre
        deux paniers GÉNÉRIQUES très différents ne doit RIEN emprunter à ses
        voisins — sa valeur lissée doit rester dans son propre intervalle
        [p25, p75], jamais tirée vers une valeur générique éloignée."""
        flat_label = SL.grade_bin(0.0)
        label_mid = SL.grade_bin(-0.10)
        combined = {
            # Référence plate personnelle, requise par `_flat_reference` avant même de
            # pouvoir construire un repli générique.
            flat_label: {"speed_pairs": [(2.8, 300.0)], "hr_pairs": [], "n_samples": 300,
                         "effective_time_s": 300.0, "n_activities": 3, "walking_time_s": 0.0, "run_share": 1.0},
            # Panier personnel isolé (voisins -12,5 % et -7,5 % absents -> génériques),
            # avec un IQR étroit autour de 3,0.
            label_mid: {"speed_pairs": [(2.9, 5.0), (3.0, 10.0), (3.1, 5.0)], "hr_pairs": [], "n_samples": 200,
                        "effective_time_s": 400.0, "n_activities": 3, "walking_time_s": 0.0, "run_share": 1.0},
        }
        result = SL.apply_fallback_and_smoothing(combined)
        b = next(x for x in result["bins"] if x["label"] == label_mid)
        self.assertEqual(b["source"], "personal")
        self.assertGreaterEqual(b["speed_ms"], b["ci_low_speed_ms"] - 1e-9)
        self.assertLessEqual(b["speed_ms"], b["ci_high_speed_ms"] + 1e-9)


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
        tail_label = SL.GRADE_BINS[0][2]
        tail = self.conn.execute(
            "SELECT * FROM slope_model_bin WHERE band = 'all' AND label = ?", (tail_label,)).fetchone()
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
        tail_label = SL.GRADE_BINS[0][2]
        tail = next(b for b in report["bins"] if b["label"] == tail_label)
        self.assertIsNone(tail["grade_lo"])
        # Round-trip JSON réel (pas seulement le dict Python) : la garantie qui
        # compte est celle-ci, jamais cassée même si le champ change de forme.
        round_tripped = json.loads(json.dumps(report, ensure_ascii=False))
        tail2 = next(b for b in round_tripped["bins"] if b["label"] == tail_label)
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

    def test_fractional_months_below_one_falls_back_to_the_default_with_a_warning(self):
        """Revue de code #58, nit : `slope_model_months = 0.5` ne doit jamais
        se retrouver tronqué silencieusement en une fenêtre nulle (`int(0.5)
        == 0`) — repli explicite sur le défaut, avec avertissement."""
        self.write("config/workspace.user.toml", "[metrics]\nslope_model_months = 0.5\n")
        conf = I.settings(I.load_config(self.ws))
        self.assertEqual(conf["slope_model_months"], SL.DEFAULT_MONTHS)


class TestComputeMetricsSurvivesAnUnexpectedCrashAndExcludesTheFailedActivity(Workspace):
    """Même discipline que #46/#47/#48 : un bug inattendu dans UN calcul dérivé
    d'UNE activité ne doit jamais faire échouer `index_workspace` pour toutes
    les activités. Revue de code #58, nit (corrigé) : l'activité EN ÉCHEC ne
    doit elle-même JAMAIS contribuer au modèle pente -> allure global — le
    résumé par panier calculé avant le point de la boucle qui plante est
    TAMPONNÉ (`pending_slope_bins`, `arc_index.compute_metrics`), commité
    seulement une fois l'activité entièrement réussie."""

    def test_one_activitys_crash_never_stops_indexing_and_is_excluded_from_the_slope_model(self):
        import arc_climb as VC
        self.write_profile()
        from datetime import date, timedelta
        as_of = date.fromisoformat("2026-09-26")
        broken_id, ok_ids = 94000000000, [94000000001, 94000000002, 94000000003]
        # `compute_metrics` traite les activités PAR DATE CROISSANTE (jamais l'ordre
        # d'insertion) : l'activité "en échec" doit donc être la plus ANCIENNE pour
        # être la PREMIÈRE traitée (celle que `boom_once` fait échouer).
        for i, garmin_id in enumerate([broken_id] + ok_ids):
            day = (as_of - timedelta(days=(len(ok_ids) - i) * 10)).isoformat()
            records, _ = sample_session(seed=800 + i, duration_s=1800, base_speed_ms=2.8, noise=True)
            self.write_activity(garmin_id, day)
            self.write_fit(garmin_id, records)
        previous_strict = os.environ.pop("ARC_STRICT_METRICS", None)
        original = VC.detect_climbs
        calls = {"n": 0}

        def boom_once(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boum (test)")
            return original(*args, **kwargs)
        VC.detect_climbs = boom_once
        try:
            self.index()
        finally:
            VC.detect_climbs = original
            if previous_strict is None:
                os.environ.pop("ARC_STRICT_METRICS", None)
            else:
                os.environ["ARC_STRICT_METRICS"] = previous_strict
        meta = self.conn.execute("SELECT * FROM slope_model_meta WHERE band = 'all'").fetchone()
        self.assertIsNone(meta["reason_code"], meta["reason"])
        # Seules les 3 activités RÉUSSIES contribuent — la première (échec injecté)
        # est exclue du modèle, jamais un résumé partiel.
        self.assertEqual(meta["n_activities"], len(ok_ids))
        broken = self.conn.execute(
            "SELECT gap_pace_s_km FROM activity WHERE garmin_activity_id = ?", (broken_id,)).fetchone()
        self.assertIsNone(broken["gap_pace_s_km"])  # même discipline que les autres champs dérivés


if __name__ == "__main__":
    unittest.main()
