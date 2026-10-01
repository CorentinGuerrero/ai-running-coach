"""Palier D — dépense énergétique modèle : intégration index/CLI/contrat.
Le moteur pur lui-même (`arc_energy.py`) est couvert par
`tests/data/test_arc_energy.py` — ce fichier couvre :

- table `activity_energy` (jointure par `activity_id` INTERNE, comme
  `activity_descent_class`/`activity_climb`, jamais `garmin_activity_id`) —
  remplie depuis `activity_sample`, restreinte à la famille course à pied
  (`arc_metrics.SPORT_FAMILY` = "run") avec échantillons FIT ingérés ;
- `resolve_weight_kg_as_of` : santé > nutrition > profil, date antérieure ou
  égale UNIQUEMENT (jamais une pesée future), la source la plus RÉCENTE gagne
  (santé prioritaire à date égale), pesées IMPLAUSIBLES (0/500 kg,
  `arc_contract.BODY_WEIGHT_KG_PLAUSIBLE`) ignorées avec repli sur la source
  suivante — jamais `weight_kg=0` ; conversion livre -> kg du profil impérial
  (`arc_legacy.parse_weight_kg`) ;
- rattachement FIT-avant-Markdown (même discipline que GAP/#44) ;
- try/except SÉPARÉ (revue de code, BLOQUANT) : un crash GAP/VAM/descente/
  durabilité ne prive jamais la séance de sa ligne `activity_energy`, et
  réciproquement (`ARC_STRICT_METRICS` respecté des deux côtés) ;
- CLI `arc_index.py energy` (`--activity`/`--date`/`--since`/`--limit`/
  `--assumptions`, incompatibilités mutuelles — y compris `--limit` avec un
  sélecteur et positionnel+`--activity` — JSON, stdout capturé) ;
- `delta_reason`/`net_reason` (`calories_kcal`/`calories_bmr_kcal` absents),
  arrondi à 1 décimale des kcal/pourcentages, séance Intervals.icu sans FIT
  téléchargé (`reason_code="no_samples"`) dans le listing par défaut ;
- contrat `calories_bmr_kcal` (valide, négatif, > calories_kcal).
- `activity_energy_report_by_id` (id interne inconnu, séance sans
  `garmin_activity_id`) et `energy_trend` (regroupement route/trail, marche/
  randonnée hors des deux paniers, fenêtre vide, un seul point, bornes de la
  fenêtre glissante) — base en mémoire, mêmes fixtures que ci-dessus.
- `energy_calibration` (calibration personnelle, PRÉVISIONS uniquement) :
  seuil `CALIBRATION_MIN_N`, statuts `insufficient`/`not_needed`/`applied`,
  exclusion des séances `flag`, paniers route/trail indépendants, randonnée
  hors des deux, fenêtre par défaut/override, `calibration` exposé par
  `energy_trend`.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import statistics
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import arc_contract as C  # noqa: E402
import arc_energy as EN  # noqa: E402
import arc_index as I  # noqa: E402


def _flat_run_records(*, duration_s=1800, speed_ms=3.0, resolution_s=5.0, altitude_m=0.0):
    """Séance synthétique plate, vitesse constante — vérité connue simple pour
    l'intégration index/CLI (le modèle lui-même est vérifié à la valeur près
    par `tests/data/test_arc_energy.py`)."""
    out = []
    t, dist = 0.0, 0.0
    n = int(duration_s // resolution_s) + 1
    for _ in range(n):
        out.append({"t_s": t, "distance_m": round(dist, 2), "altitude_m": altitude_m,
                     "speed_ms": speed_ms, "hr_bpm": 140.0, "cadence_spm": 165.0})
        t += resolution_s
        dist += speed_ms * resolution_s
    return out


def _arc_activity(kind_line: str) -> str:
    return f"# Titre\n\n```arc\n{kind_line}\n```\n\nTexte du coach.\n"


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="arc-energy-index-"))
        self.ws = self.tmp / "ws"
        for d in ("activities", "medical", "nutrition", "planning", "rapports"):
            (self.ws / d).mkdir(parents=True)
        self.conn = I.open_db(self.ws, memory=True)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def index(self, today="2026-09-25"):
        return I.index_workspace(self.conn, self.ws, today)

    def write(self, rel: str, text: str) -> None:
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_activity(self, garmin_id, day="2026-09-20", duration_s=1800, distance_m=5400,
                        sport="trail", calories_kcal=None, calories_bmr_kcal=None, extra=""):
        fields = (f'"arc": 1, "kind": "activity", "date": "{day}", "sport": "{sport}", '
                  f'"duration_s": {duration_s}, "distance_m": {distance_m}, '
                  f'"garmin_activity_id": {garmin_id}')
        if calories_kcal is not None:
            fields += f', "calories_kcal": {calories_kcal}'
        if calories_bmr_kcal is not None:
            fields += f', "calories_bmr_kcal": {calories_bmr_kcal}'
        fields += extra
        self.write(f"activities/{day}_{sport}.md", _arc_activity("{" + fields + "}"))

    def write_fit(self, garmin_id, records):
        fit_dir = self.ws / "activities/fit"
        fit_dir.mkdir(parents=True, exist_ok=True)
        (fit_dir / f"{garmin_id}.json").write_text(
            json.dumps({"activity_id": garmin_id, "records": records}), encoding="utf-8")

    def write_health_weight(self, day, weight_kg):
        self.write(f"medical/{day}_health.md", _arc_activity(
            f'{{"arc": 1, "kind": "health", "date": "{day}", "morning_check": "full", '
            f'"weight_kg": {weight_kg}}}'))

    def write_nutrition_weight(self, day, weight_kg):
        self.write(f"nutrition/{day}_nutrition.md", _arc_activity(
            f'{{"arc": 1, "kind": "nutrition", "date": "{day}", "weight_kg": {weight_kg}}}'))

    def write_profile_weight(self, weight_kg, unit="kg"):
        self.write("planning/Runner_Profile.md", f"# Profil\n\n- **Poids de forme** : {weight_kg} {unit}\n")

    def write_activity_no_garmin_id(self, intervals_id, day="2026-09-20", duration_s=1800,
                                     distance_m=5400, sport="trail", calories_kcal=None):
        """Séance synchronisée depuis Intervals.icu (#68) : `intervals_activity_id`
        (chaîne) à la place de `garmin_activity_id`, SANS FIT téléchargé
        (`fit-download --source intervals`), voir `_energy_reason_for_missing_row`."""
        fields = (f'"arc": 1, "kind": "activity", "date": "{day}", "sport": "{sport}", '
                  f'"duration_s": {duration_s}, "distance_m": {distance_m}, '
                  f'"intervals_activity_id": "{intervals_id}"')
        if calories_kcal is not None:
            fields += f', "calories_kcal": {calories_kcal}'
        self.write(f"activities/{day}_{sport}.md", _arc_activity("{" + fields + "}"))

    def activity_row(self, garmin_id):
        return self.conn.execute(
            "SELECT * FROM activity WHERE garmin_activity_id = ?", (garmin_id,)).fetchone()

    def energy_row(self, activity_id):
        return self.conn.execute(
            "SELECT * FROM activity_energy WHERE activity_id = ?", (activity_id,)).fetchone()


# ---------------------------------------------------------------------------
# Table `activity_energy` : remplissage, restriction, jointure interne.
# ---------------------------------------------------------------------------


class TestActivityEnergyTable(Workspace):
    GARMIN_ID = 90000000600

    def test_flat_run_with_weight_fills_a_row(self):
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, calories_kcal=500)
        self.write_fit(self.GARMIN_ID, _flat_run_records())
        self.index()
        act = self.activity_row(self.GARMIN_ID)
        row = self.energy_row(act["id"])
        self.assertIsNotNone(row)
        self.assertEqual(row["model_id"], EN.MODEL_ID)
        self.assertIsNotNone(row["model_kcal"])
        self.assertGreater(row["model_kcal"], 0.0)
        self.assertEqual(row["weight_kg"], 70.0)
        self.assertEqual(row["weight_source"], "profile")
        self.assertIsNone(row["reason"])
        self.assertIsNone(row["reason_code"])
        # Toute la séance est plate et courue : le flat concentre le temps/kcal.
        self.assertAlmostEqual(row["flat_s"], 1800.0, delta=5.0)
        self.assertEqual(row["uphill_s"], 0.0)

    def test_no_weight_anywhere_still_inserts_a_row_with_a_reason(self):
        """Poids introuvable (aucun profil, aucune pesée santé/nutrition) : une
        ligne EST insérée (décision documentée, contrairement à une activité
        hors famille/sans FIT qui n'en a aucune), `model_kcal` NULL, raison
        explicite — jamais une exception, jamais une ligne muette."""
        self.write_activity(self.GARMIN_ID, calories_kcal=500)
        self.write_fit(self.GARMIN_ID, _flat_run_records())
        self.index()
        act = self.activity_row(self.GARMIN_ID)
        row = self.energy_row(act["id"])
        self.assertIsNotNone(row)
        self.assertIsNone(row["model_kcal"])
        self.assertIsNone(row["weight_kg"])
        self.assertIsNone(row["weight_source"])
        self.assertEqual(row["reason_code"], "no_weight")
        self.assertIsNotNone(row["reason"])

    def test_non_run_family_sport_has_no_row_even_with_weight_and_samples(self):
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, sport="strength", calories_kcal=300)
        self.write_fit(self.GARMIN_ID, _flat_run_records())
        self.index()
        act = self.activity_row(self.GARMIN_ID)
        self.assertIsNone(self.energy_row(act["id"]))

    def test_walking_sport_is_eligible(self):
        """Le moteur gère la marche : `walking` doit obtenir une ligne,
        comme running/trail/hiking."""
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, sport="walking",
                             duration_s=3600, distance_m=5000, calories_kcal=350)
        self.write_fit(self.GARMIN_ID, _flat_run_records(duration_s=3600, speed_ms=1.4))
        self.index()
        act = self.activity_row(self.GARMIN_ID)
        row = self.energy_row(act["id"])
        self.assertIsNotNone(row)
        self.assertIsNotNone(row["model_kcal"])
        self.assertGreater(row["walk_s"], 0.0)

    def test_no_fit_samples_has_no_row(self):
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, calories_kcal=500)
        self.index()
        act = self.activity_row(self.GARMIN_ID)
        self.assertIsNone(self.energy_row(act["id"]))

    def test_fit_arrives_before_markdown_still_attaches_by_garmin_activity_id(self):
        """Même discipline que GAP/#44 (`ingest_samples`) : le FIT peut être
        déposé AVANT le fichier Markdown de l'activité — le rattachement se
        fait par `garmin_activity_id`, jamais un rowid, et une réindexation
        suffit à peupler `activity_energy` dès que les deux sont présents."""
        self.write_fit(self.GARMIN_ID, _flat_run_records())
        self.index()  # FIT seul : aucune activité connue, rien à calculer
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, calories_kcal=500)
        self.index()  # Markdown écrit : le FIT déjà ingéré est maintenant rattaché
        act = self.activity_row(self.GARMIN_ID)
        row = self.energy_row(act["id"])
        self.assertIsNotNone(row)
        self.assertIsNotNone(row["model_kcal"])

    def test_implausible_weight_falls_back_and_never_shows_zero(self):
        """Une pesée santé à 0 kg à la date de la séance ne doit jamais produire
        `weight_kg=0` en base — repli sur le profil plausible (revue de code)."""
        self.write_health_weight("2026-09-20", 0)
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, calories_kcal=500)
        self.write_fit(self.GARMIN_ID, _flat_run_records())
        self.index()
        act = self.activity_row(self.GARMIN_ID)
        row = self.energy_row(act["id"])
        self.assertEqual(row["weight_kg"], 70.0)
        self.assertEqual(row["weight_source"], "profile")
        self.assertNotEqual(row["weight_kg"], 0)

    def test_reindexing_recomputes_the_row_in_full(self):
        """Recalcul INTÉGRAL à chaque passage (même discipline que
        `activity_descent_class`) : un changement de profil (poids) se
        répercute sans étape à part."""
        self.write_profile_weight(60)
        self.write_activity(self.GARMIN_ID, calories_kcal=500)
        self.write_fit(self.GARMIN_ID, _flat_run_records())
        self.index()
        act = self.activity_row(self.GARMIN_ID)
        first_kcal = self.energy_row(act["id"])["model_kcal"]
        self.write_profile_weight(90)
        self.index()
        second_kcal = self.energy_row(act["id"])["model_kcal"]
        self.assertGreater(second_kcal, first_kcal)


# ---------------------------------------------------------------------------
# `resolve_weight_kg_as_of` : précédence santé/nutrition/profil.
# ---------------------------------------------------------------------------


class TestResolveWeightKgAsOf(Workspace):
    def test_health_wins_on_the_same_date_as_nutrition(self):
        self.write_health_weight("2026-09-20", 68.0)
        self.write_nutrition_weight("2026-09-20", 71.0)
        self.index()
        athlete = dict(self.conn.execute("SELECT * FROM athlete LIMIT 1").fetchone() or {})
        weight, source = I.resolve_weight_kg_as_of(self.conn, "2026-09-20", athlete)
        self.assertEqual(weight, 68.0)
        self.assertEqual(source, "health_day")

    def test_most_recent_source_wins_across_different_dates(self):
        """Une pesée nutrition PLUS RÉCENTE qu'une pesée santé antérieure doit
        gagner (« dernière valeur connue »), pas systématiquement la santé."""
        self.write_health_weight("2026-09-10", 70.0)
        self.write_nutrition_weight("2026-09-18", 68.0)
        self.index()
        athlete = dict(self.conn.execute("SELECT * FROM athlete LIMIT 1").fetchone() or {})
        weight, source = I.resolve_weight_kg_as_of(self.conn, "2026-09-20", athlete)
        self.assertEqual(weight, 68.0)
        self.assertEqual(source, "nutrition_day")

    def test_a_future_weighing_is_never_used(self):
        """Une pesée POSTÉRIEURE à la date de la séance n'est jamais utilisée —
        seule une pesée à la date de la séance ou avant compte."""
        self.write_health_weight("2026-09-25", 65.0)  # après la séance du 20
        self.write_profile_weight(72)
        self.index()
        athlete = dict(self.conn.execute("SELECT * FROM athlete LIMIT 1").fetchone() or {})
        weight, source = I.resolve_weight_kg_as_of(self.conn, "2026-09-20", athlete)
        self.assertEqual(weight, 72.0)
        self.assertEqual(source, "profile")

    def test_falls_back_to_profile_when_no_weighing_exists(self):
        self.write_profile_weight(75)
        self.index()
        athlete = dict(self.conn.execute("SELECT * FROM athlete LIMIT 1").fetchone() or {})
        weight, source = I.resolve_weight_kg_as_of(self.conn, "2026-09-20", athlete)
        self.assertEqual(weight, 75.0)
        self.assertEqual(source, "profile")

    def test_no_weight_anywhere_returns_none_none(self):
        self.index()
        athlete = dict(self.conn.execute("SELECT * FROM athlete LIMIT 1").fetchone() or {})
        weight, source = I.resolve_weight_kg_as_of(self.conn, "2026-09-20", athlete)
        self.assertIsNone(weight)
        self.assertIsNone(source)

    def test_zero_kg_health_weighing_is_ignored_falls_back_to_profile(self):
        """Revue de code : 0 kg est une valeur SAISIE (pas absente) mais
        implausible (`arc_contract.BODY_WEIGHT_KG_PLAUSIBLE`, 30-200 kg) — ne
        doit JAMAIS être utilisée telle quelle, ni faire `reason_code=no_weight`
        alors qu'un profil plausible existe."""
        self.write_health_weight("2026-09-20", 0)
        self.write_profile_weight(70)
        self.index()
        athlete = dict(self.conn.execute("SELECT * FROM athlete LIMIT 1").fetchone() or {})
        weight, source = I.resolve_weight_kg_as_of(self.conn, "2026-09-20", athlete)
        self.assertEqual(weight, 70.0)
        self.assertEqual(source, "profile")

    def test_500_kg_nutrition_weighing_is_ignored_falls_back_to_earlier_plausible_health(self):
        """Une pesée nutrition aberrante (500 kg, faute de frappe/export cassé) à
        la date la plus récente ne doit jamais l'emporter sur une pesée santé
        PLUS ANCIENNE mais plausible — retombe sur la valeur plausible
        précédente, jamais sur `(None, None)` ni sur la valeur aberrante."""
        self.write_health_weight("2026-09-10", 68.0)
        self.write_nutrition_weight("2026-09-19", 500)
        self.index()
        athlete = dict(self.conn.execute("SELECT * FROM athlete LIMIT 1").fetchone() or {})
        weight, source = I.resolve_weight_kg_as_of(self.conn, "2026-09-20", athlete)
        self.assertEqual(weight, 68.0)
        self.assertEqual(source, "health_day")

    def test_implausible_profile_weight_is_never_used(self):
        """Un profil à 0 kg (mal rempli) ne doit jamais fausser silencieusement
        TOUTES les séances faute de pesée santé/nutrition — repli sur
        `(None, None)`, jamais `weight_kg=0`."""
        self.write_profile_weight(0)
        self.index()
        athlete = dict(self.conn.execute("SELECT * FROM athlete LIMIT 1").fetchone() or {})
        weight, source = I.resolve_weight_kg_as_of(self.conn, "2026-09-20", athlete)
        self.assertIsNone(weight)
        self.assertIsNone(source)

    def test_500_kg_profile_weight_is_never_used(self):
        self.write_profile_weight(500)
        self.index()
        athlete = dict(self.conn.execute("SELECT * FROM athlete LIMIT 1").fetchone() or {})
        weight, source = I.resolve_weight_kg_as_of(self.conn, "2026-09-20", athlete)
        self.assertIsNone(weight)
        self.assertIsNone(source)

    def test_profile_weight_in_pounds_is_converted_to_kg(self):
        """Revue de code : un profil imperial peut porter le poids en livres
        (« 154 lb ») — converti par `arc_legacy.parse_weight_kg`, jamais lu tel
        quel comme des kg (ce qui donnerait un poids plus de deux fois trop
        lourd)."""
        self.write_profile_weight(154, unit="lb")
        self.index()
        athlete = dict(self.conn.execute("SELECT * FROM athlete LIMIT 1").fetchone() or {})
        weight, source = I.resolve_weight_kg_as_of(self.conn, "2026-09-20", athlete)
        self.assertAlmostEqual(weight, 154 * 0.45359237, places=2)
        self.assertEqual(source, "profile")


class TestParseWeightKg(unittest.TestCase):
    """`arc_legacy.parse_weight_kg` : seule l'unité du PREMIER nombre compte
    (revue de code — une mention « lb » ailleurs dans la puce ne convertit rien)."""

    def test_mixed_units_keep_first_number_unit(self):
        import arc_legacy as L  # noqa: E402
        cases = {
            "72 kg (159 lb)": 72.0,
            "72 kg — objectif 150 lbs": 72.0,
            "Poids 70 kg, lb": 70.0,
            "154 lb": 69.85,
            "154lbs": 69.85,
            "70,5": 70.5,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertAlmostEqual(L.parse_weight_kg(text), expected, places=2)


# ---------------------------------------------------------------------------
# CLI `arc_index.py energy`.
# ---------------------------------------------------------------------------


class TestEnergyCli(Workspace):
    GARMIN_ID = 90000000601

    def _run_cli(self, argv):
        """Exécute `I.main(argv)` en capturant stdout — jamais laisser le JSON
        produit par la CLI polluer la sortie de la suite de tests (revue de
        code) — et rend `(code, parsed_json)`."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = I.main(argv)
        return code, json.loads(buf.getvalue())

    def test_cli_activity_selector(self):
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, calories_kcal=500, calories_bmr_kcal=80)
        self.write_fit(self.GARMIN_ID, _flat_run_records())
        self.index()
        code, out = self._run_cli(["energy", "--activity", str(self.GARMIN_ID),
                                    "--workspace", str(self.ws), "--memory"])
        self.assertEqual(code, 0)
        self.assertEqual(out["model_id"], EN.MODEL_ID)
        self.assertEqual(len(out["sessions"]), 1)
        session = out["sessions"][0]
        self.assertEqual(session["garmin_activity_id"], self.GARMIN_ID)
        self.assertIsNotNone(session["model_kcal"])

    def test_cli_assumptions_flag_toggles_full_vs_summary(self):
        self.write_activity(self.GARMIN_ID, calories_kcal=400)
        self.index()
        code, without = self._run_cli(["energy", "--activity", str(self.GARMIN_ID),
                                        "--workspace", str(self.ws), "--memory"])
        self.assertEqual(code, 0)
        self.assertIsNone(without["assumptions"])
        self.assertIsNotNone(without["assumptions_summary"])
        code, with_full = self._run_cli(["energy", "--activity", str(self.GARMIN_ID),
                                          "--workspace", str(self.ws), "--memory", "--assumptions"])
        self.assertEqual(code, 0)
        self.assertIsNone(with_full["assumptions_summary"])
        self.assertEqual(with_full["assumptions"], EN.ASSUMPTIONS)

    def test_report_shape_and_delta_flag(self):
        self.write_profile_weight(70)
        # `calories_kcal` volontairement très bas pour garantir |delta| > 15 %.
        self.write_activity(self.GARMIN_ID, calories_kcal=50, calories_bmr_kcal=20)
        self.write_fit(self.GARMIN_ID, _flat_run_records())
        self.index()
        out = I.energy_report(self.conn, activity=self.GARMIN_ID)
        self.assertEqual(out["model_id"], EN.MODEL_ID)
        self.assertIsNone(out["assumptions"])
        self.assertIsNotNone(out["assumptions_summary"])
        self.assertEqual(len(out["sessions"]), 1)
        session = out["sessions"][0]
        self.assertEqual(session["garmin_kcal"], 50.0)
        self.assertEqual(session["bmr_kcal"], 20.0)
        self.assertEqual(session["net_garmin_kcal"], 30.0)
        self.assertIsNotNone(session["model_kcal"])
        self.assertIsNotNone(session["net_model_kcal"])
        self.assertIsNone(session["delta_reason"])
        self.assertIsNone(session["net_reason"])
        self.assertTrue(session["flag"])
        self.assertIn("breakdown", session)
        # Arrondi à 1 décimale (revue de code) — jamais la précision flottante brute.
        self.assertEqual(round(session["delta_pct"], 1), session["delta_pct"])
        self.assertEqual(round(session["net_model_kcal"], 1), session["net_model_kcal"])

    def test_missing_garmin_kcal_sets_delta_reason(self):
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, calories_bmr_kcal=80)  # pas de calories_kcal
        self.write_fit(self.GARMIN_ID, _flat_run_records())
        self.index()
        session = I.energy_report(self.conn, activity=self.GARMIN_ID)["sessions"][0]
        self.assertIsNone(session["garmin_kcal"])
        self.assertIsNone(session["delta_pct"])
        self.assertIsNone(session["flag"])
        self.assertEqual(session["delta_reason"], "no_garmin_kcal")
        self.assertIsNotNone(session["model_kcal"])  # le modèle, lui, reste calculable

    def test_missing_bmr_sets_net_reason(self):
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, calories_kcal=500)  # pas de calories_bmr_kcal
        self.write_fit(self.GARMIN_ID, _flat_run_records())
        self.index()
        session = I.energy_report(self.conn, activity=self.GARMIN_ID)["sessions"][0]
        self.assertIsNone(session["bmr_kcal"])
        self.assertIsNone(session["net_garmin_kcal"])
        self.assertIsNone(session["net_model_kcal"])
        self.assertEqual(session["net_reason"], "no_bmr")

    def test_session_without_garmin_id_appears_in_listing_with_explicit_reason(self):
        """Revue de code : une séance synchronisée depuis Intervals.icu (#68, pas
        de `garmin_activity_id`) doit apparaître dans le listing par défaut (même
        famille de sport), pas disparaître silencieusement — avec
        `reason_code="no_samples"` tant que son FIT n'est pas téléchargé
        (`fit-download --source intervals`). Une séance sans AUCUN identifiant
        externe est `"no_activity_id"`, voir `tests/data/test_intervals_samples.py`."""
        self.write_profile_weight(70)
        self.write_activity_no_garmin_id("i123456", day="2026-09-20", calories_kcal=400)
        self.index()
        out = I.energy_report(self.conn)
        self.assertEqual(len(out["sessions"]), 1)
        session = out["sessions"][0]
        self.assertIsNone(session["garmin_activity_id"])
        self.assertEqual(session["reason_code"], "no_samples")
        self.assertIsNone(session["model_kcal"])

    def test_unknown_activity_has_an_explicit_reason(self):
        self.index()
        out = I.energy_report(self.conn, activity=123456)
        session = out["sessions"][0]
        self.assertIsNone(session["model_kcal"])
        self.assertEqual(session["reason_code"], "unknown_activity")

    def test_non_run_family_activity_has_an_explicit_reason_via_activity_selector(self):
        self.write_activity(self.GARMIN_ID, sport="strength", calories_kcal=300)
        self.write_fit(self.GARMIN_ID, _flat_run_records())
        self.index()
        out = I.energy_report(self.conn, activity=self.GARMIN_ID)
        session = out["sessions"][0]
        self.assertEqual(session["reason_code"], "not_run_family")

    def test_no_samples_activity_has_an_explicit_reason(self):
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, calories_kcal=500)
        self.index()
        out = I.energy_report(self.conn, activity=self.GARMIN_ID)
        session = out["sessions"][0]
        self.assertEqual(session["reason_code"], "no_samples")

    def test_default_listing_excludes_non_eligible_sports(self):
        self.write_profile_weight(70)
        self.write_activity(90000000602, day="2026-09-18", sport="strength", calories_kcal=300)
        self.write_activity(90000000603, day="2026-09-19", sport="trail", calories_kcal=500)
        self.write_fit(90000000603, _flat_run_records())
        self.index()
        out = I.energy_report(self.conn)
        garmin_ids = {s["garmin_activity_id"] for s in out["sessions"]}
        self.assertIn(90000000603, garmin_ids)
        self.assertNotIn(90000000602, garmin_ids)

    def test_default_listing_respects_limit_and_chronological_order(self):
        self.write_profile_weight(70)
        for i, day in enumerate(["2026-09-15", "2026-09-16", "2026-09-17"]):
            gid = 90000000700 + i
            self.write_activity(gid, day=day, calories_kcal=400)
            self.write_fit(gid, _flat_run_records())
        self.index()
        out = I.energy_report(self.conn, limit=2)
        self.assertEqual(len(out["sessions"]), 2)
        dates = [s["date"] for s in out["sessions"]]
        self.assertEqual(dates, sorted(dates))  # chronologique, la plus récente en dernier
        self.assertEqual(dates, ["2026-09-16", "2026-09-17"])

    def test_date_selector_filters_to_that_day_only(self):
        self.write_profile_weight(70)
        self.write_activity(90000000710, day="2026-09-18", calories_kcal=400)
        self.write_activity(90000000711, day="2026-09-19", calories_kcal=400)
        self.write_fit(90000000710, _flat_run_records())
        self.write_fit(90000000711, _flat_run_records())
        self.index()
        out = I.energy_report(self.conn, day="2026-09-19")
        self.assertEqual([s["garmin_activity_id"] for s in out["sessions"]], [90000000711])

    def test_since_selector_is_inclusive_and_chronological(self):
        self.write_profile_weight(70)
        for i, day in enumerate(["2026-09-10", "2026-09-18", "2026-09-19"]):
            gid = 90000000720 + i
            self.write_activity(gid, day=day, calories_kcal=400)
            self.write_fit(gid, _flat_run_records())
        self.index()
        out = I.energy_report(self.conn, since="2026-09-18")
        self.assertEqual([s["date"] for s in out["sessions"]], ["2026-09-18", "2026-09-19"])

    def test_cli_rejects_combining_activity_and_date(self):
        self.write_activity(self.GARMIN_ID, calories_kcal=400)
        self.index()
        with self.assertRaises(I.ConfigError):
            I.main(["energy", "--activity", str(self.GARMIN_ID), "--date", "2026-09-20",
                    "--workspace", str(self.ws), "--memory"])

    def test_cli_rejects_combining_date_and_since(self):
        self.index()
        with self.assertRaises(I.ConfigError):
            I.main(["energy", "--date", "2026-09-20", "--since", "2026-09-10",
                    "--workspace", str(self.ws), "--memory"])

    def test_cli_rejects_limit_combined_with_activity_selector(self):
        self.write_activity(self.GARMIN_ID, calories_kcal=400)
        self.index()
        with self.assertRaises(I.ConfigError):
            I.main(["energy", "--activity", str(self.GARMIN_ID), "--limit", "3",
                    "--workspace", str(self.ws), "--memory"])

    def test_cli_rejects_limit_combined_with_date_selector(self):
        self.index()
        with self.assertRaises(I.ConfigError):
            I.main(["energy", "--date", "2026-09-20", "--limit", "3",
                    "--workspace", str(self.ws), "--memory"])

    def test_cli_rejects_positional_and_activity_flag_together(self):
        self.write_activity(self.GARMIN_ID, calories_kcal=400)
        self.index()
        with self.assertRaises(I.ConfigError):
            I.main(["energy", str(self.GARMIN_ID), "--activity", str(self.GARMIN_ID),
                    "--workspace", str(self.ws), "--memory"])

    def test_cli_calibration_flag_returns_the_calibration_report(self):
        self.index()
        code, out = self._run_cli(["energy", "--calibration", "--weeks", "12",
                                    "--workspace", str(self.ws), "--memory"])
        self.assertEqual(code, 0)
        self.assertEqual(out["window_weeks"], 12)
        self.assertEqual(out["min_n"], EN.CALIBRATION_MIN_N)
        self.assertIn("route", out["buckets"])
        self.assertIn("trail", out["buckets"])

    def test_cli_calibration_rejects_activity_selector(self):
        self.index()
        with self.assertRaises(I.ConfigError):
            I.main(["energy", "--calibration", "--activity", str(self.GARMIN_ID),
                    "--workspace", str(self.ws), "--memory"])

    def test_cli_calibration_rejects_assumptions_flag(self):
        self.index()
        with self.assertRaises(I.ConfigError):
            I.main(["energy", "--calibration", "--assumptions",
                    "--workspace", str(self.ws), "--memory"])

    def test_cli_calibration_rejects_limit(self):
        self.index()
        with self.assertRaises(I.ConfigError):
            I.main(["energy", "--calibration", "--limit", "5",
                    "--workspace", str(self.ws), "--memory"])


# ---------------------------------------------------------------------------
# Try/except SÉPARÉ (revue de code) : GAP/VAM/descente/durabilité d'un
# côté, énergie de l'autre — un échec de l'un ne doit jamais affecter l'autre.
# ---------------------------------------------------------------------------


class TestEnergyTryExceptIsIndependentFromGapBlock(Workspace):
    GARMIN_ID = 90000000900

    def setUp(self):
        super().setUp()
        self._previous_strict = os.environ.pop("ARC_STRICT_METRICS", None)

    def tearDown(self):
        if self._previous_strict is None:
            os.environ.pop("ARC_STRICT_METRICS", None)
        else:
            os.environ["ARC_STRICT_METRICS"] = self._previous_strict
        super().tearDown()

    def test_a_gap_crash_never_prevents_the_energy_row(self):
        """Un détecteur GAP qui lève ne doit jamais priver la séance de sa ligne
        `activity_energy` — les deux try/except sont désormais INDÉPENDANTS
        (revue de code, correctif BLOQUANT)."""
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, calories_kcal=500)
        self.write_fit(self.GARMIN_ID, _flat_run_records())

        original = I.G.gap_sample_series

        def _boom(*args, **kwargs):
            raise RuntimeError("bug injecté par le test")

        I.G.gap_sample_series = _boom
        try:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.index()
        finally:
            I.G.gap_sample_series = original

        self.assertIn("bug injecté par le test", stderr.getvalue())
        act = self.activity_row(self.GARMIN_ID)
        # GAP/découplage/etc. : bien remis à NULL (comportement INCHANGÉ de ce bloc).
        self.assertIsNone(act["gap_pace_s_km"])
        self.assertIsNone(act["decoupling_pct"])
        # Énergie : NON affectée par ce crash, calculée normalement.
        row = self.energy_row(act["id"])
        self.assertIsNotNone(row)
        self.assertIsNotNone(row["model_kcal"])
        self.assertIsNone(row["reason_code"])

    def test_an_energy_crash_never_nulls_the_gap_block_columns(self):
        """Réciproquement : un crash dans le calcul d'énergie ne doit JAMAIS
        remettre à NULL `gap_pace_s_km`/`decoupling_pct`/etc. de la séance —
        seule la ligne `activity_energy` porte `reason_code="internal_error"`."""
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, calories_kcal=500)
        self.write_fit(self.GARMIN_ID, _flat_run_records())

        original = I.EN.energy_from_samples

        def _boom(*args, **kwargs):
            raise RuntimeError("bug injecté par le test, côté énergie")

        I.EN.energy_from_samples = _boom
        try:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.index()
        finally:
            I.EN.energy_from_samples = original

        self.assertIn("bug injecté par le test, côté énergie", stderr.getvalue())
        act = self.activity_row(self.GARMIN_ID)
        # GAP/découplage/etc. : NON affectés par ce crash côté énergie.
        self.assertIsNotNone(act["gap_pace_s_km"])
        # Énergie : ligne avec reason_code=internal_error, jamais d'exception globale.
        row = self.energy_row(act["id"])
        self.assertIsNotNone(row)
        self.assertIsNone(row["model_kcal"])
        self.assertEqual(row["reason_code"], "internal_error")

    def test_arc_strict_metrics_reraises_an_energy_crash(self):
        self.write_profile_weight(70)
        self.write_activity(self.GARMIN_ID, calories_kcal=500)
        self.write_fit(self.GARMIN_ID, _flat_run_records())

        original = I.EN.energy_from_samples

        def _boom(*args, **kwargs):
            raise RuntimeError("bug injecté par le test")

        os.environ["ARC_STRICT_METRICS"] = "1"
        I.EN.energy_from_samples = _boom
        try:
            with self.assertRaises(RuntimeError):
                self.index()
        finally:
            I.EN.energy_from_samples = original


# ---------------------------------------------------------------------------
# Contrat : `calories_bmr_kcal`.
# ---------------------------------------------------------------------------


class TestContractCaloriesBmrKcal(unittest.TestCase):
    def _activity(self, **overrides):
        data = {"arc": 1, "kind": "activity", "date": "2026-09-20", "sport": "trail", "duration_s": 1800}
        data.update(overrides)
        return data

    def test_valid_bmr_within_calories_passes(self):
        errors, warnings = C.validate(self._activity(calories_kcal=500, calories_bmr_kcal=80))
        self.assertEqual(errors, [])

    def test_negative_bmr_is_rejected(self):
        errors, _ = C.validate(self._activity(calories_kcal=500, calories_bmr_kcal=-10))
        self.assertTrue(any("calories_bmr_kcal" in e for e in errors))

    def test_bmr_exceeding_calories_is_rejected(self):
        errors, _ = C.validate(self._activity(calories_kcal=500, calories_bmr_kcal=600))
        self.assertTrue(any("calories_bmr_kcal" in e and "calories_kcal" in e for e in errors))

    def test_bmr_alone_without_calories_is_accepted(self):
        """Aucune règle croisée ne peut s'appliquer sans les deux valeurs — voir
        `arc_contract.validate`, jamais une exception sur une valeur absente."""
        errors, _ = C.validate(self._activity(calories_bmr_kcal=80))
        self.assertEqual(errors, [])

    def test_documented_in_skill(self):
        """Même discipline que les autres clés du contrat (`tests/data/
        test_arc_contract.py`) : chaque clé du schéma doit être documentée
        dans le skill — vérifié ici pour ne pas dépendre de l'ordre des
        modules de test."""
        skill = (REPO / "skills" / "workspace-data-contract" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("calories_bmr_kcal", skill)


# ---------------------------------------------------------------------------
# `activity_energy_report_by_id` — dépense d'UNE séance par id INTERNE
# (`/api/activity/<id>.energy`, tableau de bord local).
# ---------------------------------------------------------------------------


class TestActivityEnergyReportById(Workspace):
    def test_unknown_activity_id_reports_unknown_activity(self):
        """`activity_id` sans ligne `activity` correspondante — aucun accès disque,
        rend le même jeu de clés que toute autre séance (`_energy_session_dict`),
        jamais une exception ni une clé manquante."""
        self.index()
        report = I.activity_energy_report_by_id(self.conn, 999999)
        self.assertIsNone(report["model_kcal"])
        self.assertEqual(report["reason_code"], "unknown_activity")
        self.assertEqual(report["reason"], "activité introuvable")

    def test_intervals_activity_without_fit_reports_no_samples(self):
        """Séance synchronisée depuis Intervals.icu (#68, `intervals_activity_id`
        au lieu de `garmin_activity_id`) dont le FIT n'est pas encore téléchargé —
        `reason_code="no_samples"`, comme une séance Garmin dans le même cas (même
        règle que `_energy_reason_for_missing_row`)."""
        self.write_activity_no_garmin_id("i12345678", calories_kcal=500)
        self.index()
        row = self.conn.execute(
            "SELECT id FROM activity WHERE date = '2026-09-20'").fetchone()
        report = I.activity_energy_report_by_id(self.conn, row["id"])
        self.assertIsNone(report["model_kcal"])
        self.assertEqual(report["reason_code"], "no_samples")
        self.assertEqual(report["garmin_kcal"], 500)

    def test_matches_activity_energy_report_by_garmin_id(self):
        """Même résultat que `activity_energy_report` (id GARMIN, pour la CLI) sur
        la MÊME séance — les deux délèguent à `_energy_session_for_activity_row`,
        jamais un second calcul du delta/flag."""
        garmin_id = 90000000900
        self.write_profile_weight(70)
        self.write_activity(garmin_id, calories_kcal=450)
        self.write_fit(garmin_id, _flat_run_records())
        self.index()
        by_garmin = I.activity_energy_report(self.conn, garmin_id)
        row = self.activity_row(garmin_id)
        by_id = I.activity_energy_report_by_id(self.conn, row["id"])
        self.assertEqual(by_garmin, by_id)


# ---------------------------------------------------------------------------
# `energy_trend` — tendance modèle vs Garmin (`/api/energy-trend`, tableau de
# bord local) : fenêtre glissante, regroupement route/trail.
# ---------------------------------------------------------------------------


class TestEnergyTrend(Workspace):
    def _flat_activity(self, garmin_id, day, sport, calories_kcal, weight_kg=70):
        self.write_profile_weight(weight_kg)
        self.write_activity(garmin_id, day=day, sport=sport, calories_kcal=calories_kcal,
                            duration_s=1800, distance_m=5400)
        self.write_fit(garmin_id, _flat_run_records(duration_s=1800, speed_ms=3.0))

    def test_empty_window_returns_no_sessions_and_none_medians(self):
        """Aucune séance dans la fenêtre : `sessions`/`sessions_n`/`measured_n`
        vides plutôt qu'une exception, `delta_median_pct` à `None` des deux
        côtés — jamais 0, qui laisserait croire à un accord parfait mesuré."""
        self.index(today="2026-09-25")
        trend = I.energy_trend(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        self.assertEqual(trend["sessions"], [])
        self.assertEqual(trend["sessions_n"], 0)
        self.assertEqual(trend["measured_n"], 0)
        self.assertIsNone(trend["delta_median_pct"]["route"])
        self.assertIsNone(trend["delta_median_pct"]["trail"])

    def test_route_and_trail_are_separate_buckets(self):
        """Deux séances `running` et une `trail` : la médiane route ne mélange
        jamais le trail (et réciproquement) — vérifié par recalcul indépendant
        de la médiane à partir des `delta_pct` réellement rendus, jamais une
        valeur physique attendue à l'avance (le modèle lui-même est couvert par
        `tests/data/test_arc_energy.py`)."""
        self._flat_activity(90000001001, "2026-09-01", "running", calories_kcal=400)
        self._flat_activity(90000001002, "2026-09-02", "running", calories_kcal=420)
        self._flat_activity(90000001003, "2026-09-03", "trail", calories_kcal=500)
        self.index(today="2026-09-25")
        trend = I.energy_trend(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        route_sessions = [s for s in trend["sessions"] if s["sport"] == "running"]
        trail_sessions = [s for s in trend["sessions"] if s["sport"] == "trail"]
        self.assertEqual(len(route_sessions), 2)
        self.assertEqual(len(trail_sessions), 1)
        for s in route_sessions + trail_sessions:
            self.assertIsNotNone(s["delta_pct"])
        expected_route = round(statistics.median([s["delta_pct"] for s in route_sessions]), 1)
        expected_trail = round(trail_sessions[0]["delta_pct"], 1)
        self.assertEqual(trend["delta_median_pct"]["route"], expected_route)
        self.assertEqual(trend["delta_median_pct"]["trail"], expected_trail)

    def test_hiking_is_counted_but_excluded_from_route_trail_medians(self):
        """Randonnée : éligible au calcul (`ENERGY_ELIGIBLE_SPORTS`), présente dans
        `sessions`/`measured_n`, mais HORS des deux paniers de médiane — aucune
        référence de validation connue pour ce sport (voir
        `ENERGY_TREND_ROUTE_TRAIL_BUCKET`)."""
        self._flat_activity(90000001004, "2026-09-01", "hiking", calories_kcal=350)
        self.index(today="2026-09-25")
        trend = I.energy_trend(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        self.assertEqual(trend["sessions_n"], 1)
        self.assertEqual(trend["measured_n"], 1)
        self.assertIsNotNone(trend["sessions"][0]["delta_pct"])
        self.assertIsNone(trend["delta_median_pct"]["route"])
        self.assertIsNone(trend["delta_median_pct"]["trail"])

    def test_single_point_median_equals_its_own_value(self):
        """Médiane d'un seul point : elle-même, jamais `None` ni une moyenne
        dégénérée."""
        self._flat_activity(90000001005, "2026-09-10", "running", calories_kcal=410)
        self.index(today="2026-09-25")
        trend = I.energy_trend(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        self.assertEqual(len(trend["sessions"]), 1)
        self.assertEqual(trend["delta_median_pct"]["route"], round(trend["sessions"][0]["delta_pct"], 1))

    def test_window_boundaries_are_inclusive_start_and_end(self):
        """Fenêtre de `weeks=2` (14 j) se terminant à `today` INCLUS : une séance
        la veille du début de fenêtre est exclue, une séance au premier jour ET
        une séance datée `today` sont toutes deux incluses — jamais une borne
        décalée d'un jour dans un sens ou l'autre."""
        today = date.fromisoformat("2026-09-25")
        start = today - timedelta(days=13)
        before_start = start - timedelta(days=1)
        self._flat_activity(90000001006, before_start.isoformat(), "running", calories_kcal=400)
        self._flat_activity(90000001007, start.isoformat(), "running", calories_kcal=400)
        self._flat_activity(90000001008, today.isoformat(), "running", calories_kcal=400)
        self.index(today="2026-09-25")
        trend = I.energy_trend(self.conn, today, weeks=2)
        dates = {s["date"] for s in trend["sessions"]}
        self.assertNotIn(before_start.isoformat(), dates)
        self.assertIn(start.isoformat(), dates)
        self.assertIn(today.isoformat(), dates)


# ---------------------------------------------------------------------------
# `energy_calibration` — calibration personnelle du modèle (PRÉVISIONS
# uniquement, voir `arc_energy.ASSUMPTIONS["calibration"]`).
# ---------------------------------------------------------------------------


class TestEnergyCalibration(Workspace):
    def _route_session(self, garmin_id, day, ratio, weight_kg=70, sport="running"):
        """Séance plate (`_flat_run_records`), `calories_kcal` ajusté APRÈS un
        premier passage pour obtenir EXACTEMENT `garmin_kcal / model_kcal ==
        ratio` — jamais une valeur de `calories_kcal` devinée à la main, le
        modèle physique lui-même reste couvert par `tests/data/test_arc_energy.py`."""
        self.write_profile_weight(weight_kg)
        self.write_activity(garmin_id, day=day, sport=sport, calories_kcal=1,
                             duration_s=1800, distance_m=5400)
        self.write_fit(garmin_id, _flat_run_records(duration_s=1800, speed_ms=3.0))
        self.index(today="2026-09-25")
        act = self.activity_row(garmin_id)
        model_kcal = self.energy_row(act["id"])["model_kcal"]
        self.write_activity(garmin_id, day=day, sport=sport,
                             calories_kcal=round(model_kcal * ratio, 2),
                             duration_s=1800, distance_m=5400)

    def _days(self, n, start="2026-08-01"):
        first = date.fromisoformat(start)
        return [(first + timedelta(days=i)).isoformat() for i in range(n)]

    def test_below_min_n_is_insufficient(self):
        """`CALIBRATION_MIN_N - 1` séances route (14) : sous le seuil, même
        avec un biais net (ratio 1.10, hors bande mais SOUS le seuil de
        signalement `DELTA_ALERT_PCT`, donc jamais `flag`) —
        `status="insufficient"`, facteur 1.0."""
        n = EN.CALIBRATION_MIN_N - 1
        for i, day in enumerate(self._days(n)):
            self._route_session(90000003000 + i, day, ratio=1.10)
        self.index(today="2026-09-25")
        report = I.energy_calibration(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        route = report["buckets"]["route"]
        self.assertEqual(route["n"], n)
        self.assertEqual(route["status"], "insufficient")
        self.assertEqual(route["factor"], 1.0)

    def test_applied_with_enough_sessions_and_a_clear_bias(self):
        """`CALIBRATION_MIN_N` séances route à ratio 1.10 (10 %, hors bande de
        5 %) : `status="applied"`, facteur ≈ 1.10 (la médiane elle-même)."""
        for i, day in enumerate(self._days(EN.CALIBRATION_MIN_N)):
            self._route_session(90000003100 + i, day, ratio=1.10)
        self.index(today="2026-09-25")
        report = I.energy_calibration(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        route = report["buckets"]["route"]
        self.assertEqual(route["n"], EN.CALIBRATION_MIN_N)
        self.assertEqual(route["status"], "applied")
        self.assertAlmostEqual(route["factor"], 1.10, delta=0.01)

    def test_not_needed_when_median_is_already_close_to_one(self):
        """Même effectif suffisant, mais ratio 1.02 (2 %, sous la bande de
        5 %) : le modèle est déjà fidèle, `status="not_needed"`, facteur 1.0."""
        for i, day in enumerate(self._days(EN.CALIBRATION_MIN_N)):
            self._route_session(90000003200 + i, day, ratio=1.02)
        self.index(today="2026-09-25")
        report = I.energy_calibration(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        route = report["buckets"]["route"]
        self.assertEqual(route["status"], "not_needed")
        self.assertEqual(route["factor"], 1.0)

    def test_outlier_sessions_are_excluded_relative_to_the_bucket_median(self):
        """`CALIBRATION_MIN_N` séances propres à ratio 1.10, PLUS trois séances
        très aberrantes (ratio 2.0) : les trois aberrantes ne comptent NI dans
        `n` NI dans la médiane — exclues par `arc_energy.calibration_band_report`
        RELATIVEMENT à la médiane brute du panier (`CALIBRATION_OUTLIER_
        RELATIVE_BAND_PCT`), PAS par leur `flag` individuel (correctif de
        revue de code, BLOQUANT — `energy_calibration` ne filtre plus jamais
        sur `flag`, voir sa docstring) : un capteur manifestement défaillant ne
        doit jamais influencer la calibration des autres séances, mais ce
        n'est plus `flag` qui le décide ici."""
        days = self._days(EN.CALIBRATION_MIN_N + 3)
        for i, day in enumerate(days[:EN.CALIBRATION_MIN_N]):
            self._route_session(90000003300 + i, day, ratio=1.10)
        for i, day in enumerate(days[EN.CALIBRATION_MIN_N:]):
            self._route_session(90000003400 + i, day, ratio=2.0)  # aberrante, loin de la médiane du panier
        self.index(today="2026-09-25")
        report = I.energy_calibration(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        route = report["buckets"]["route"]
        self.assertEqual(route["n"], EN.CALIBRATION_MIN_N)
        self.assertAlmostEqual(route["factor"], 1.10, delta=0.01)

    def test_a_real_bucket_wide_bias_is_never_excluded_by_the_per_session_flag(self):
        """Correctif de revue de code (BLOQUANT) : `CALIBRATION_MIN_N` séances
        à ratio 1.20 — CHAQUE séance serait individuellement `flag=True`
        (|écart| ≈ 16,7 % > `DELTA_ALERT_PCT`, 15 %), mais le panier ENTIER
        est cohérent (aucune séance aberrante par rapport aux autres) :
        `energy_calibration` doit rendre `status="applied"`, `n` = TOUTES les
        séances (aucune exclusion), facteur ≈ 1.20 — jamais `insufficient`
        comme le faisait l'ancien mécanisme (exclusion sur `flag`, qui aurait
        exclu les `CALIBRATION_MIN_N` séances et rendu n=0)."""
        for i, day in enumerate(self._days(EN.CALIBRATION_MIN_N)):
            self._route_session(90000003800 + i, day, ratio=1.20)
        self.index(today="2026-09-25")
        report = I.energy_calibration(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        route = report["buckets"]["route"]
        self.assertEqual(route["status"], "applied")
        self.assertEqual(route["n"], EN.CALIBRATION_MIN_N)
        self.assertAlmostEqual(route["factor"], 1.20, delta=0.01)

    def test_route_and_trail_are_separate_buckets(self):
        """Route et trail calibrés INDÉPENDAMMENT, comme `energy_trend` — un
        biais route ne doit jamais influencer le panier trail."""
        for i, day in enumerate(self._days(EN.CALIBRATION_MIN_N)):
            self._route_session(90000003500 + i, day, ratio=1.10, sport="running")
        for i, day in enumerate(self._days(EN.CALIBRATION_MIN_N, start="2026-08-01")):
            self._route_session(90000003600 + i, day, ratio=0.90, sport="trail")
        self.index(today="2026-09-25")
        report = I.energy_calibration(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        self.assertEqual(report["buckets"]["route"]["status"], "applied")
        self.assertAlmostEqual(report["buckets"]["route"]["factor"], 1.10, delta=0.01)
        self.assertEqual(report["buckets"]["trail"]["status"], "applied")
        self.assertAlmostEqual(report["buckets"]["trail"]["factor"], 0.90, delta=0.01)

    def test_hiking_is_never_counted_in_either_bucket(self):
        """Randonnée : éligible au calcul du modèle, mais HORS des deux
        paniers de calibration (même restriction qu'`energy_trend` — aucune
        validation de référence connue pour ce sport)."""
        for i, day in enumerate(self._days(EN.CALIBRATION_MIN_N)):
            self._route_session(90000003700 + i, day, ratio=1.30, sport="hiking")
        self.index(today="2026-09-25")
        report = I.energy_calibration(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        self.assertEqual(report["buckets"]["route"]["n"], 0)
        self.assertEqual(report["buckets"]["trail"]["n"], 0)

    def test_empty_window_is_insufficient_for_both_buckets(self):
        """Aucune séance dans la fenêtre : les deux paniers `insufficient`,
        `n=0` — jamais une exception."""
        self.index(today="2026-09-25")
        report = I.energy_calibration(self.conn, date.fromisoformat("2026-09-25"), weeks=12)
        for bucket in ("route", "trail"):
            self.assertEqual(report["buckets"][bucket]["n"], 0)
            self.assertEqual(report["buckets"][bucket]["status"], "insufficient")

    def test_default_window_is_the_calibration_constant(self):
        """Sans `weeks` explicite, la fenêtre par défaut est
        `arc_energy.CALIBRATION_WINDOW_WEEKS` (26) — INDÉPENDANTE de
        `ENERGY_TREND_WEEKS` (12, plus courte)."""
        self.index(today="2026-09-25")
        report = I.energy_calibration(self.conn, date.fromisoformat("2026-09-25"))
        self.assertEqual(report["window_weeks"], EN.CALIBRATION_WINDOW_WEEKS)

    def test_energy_trend_carries_a_calibration_field(self):
        """`/api/energy-trend` (`energy_trend`) porte un champ `calibration`
        (statut de calibration par panier) — sur SA PROPRE fenêtre par défaut
        (26 semaines), jamais celle, plus courte, de la tendance affichée."""
        self.index(today="2026-09-25")
        trend = I.energy_trend(self.conn, date.fromisoformat("2026-09-25"), weeks=2)
        self.assertIn("calibration", trend)
        self.assertEqual(trend["calibration"]["window_weeks"], EN.CALIBRATION_WINDOW_WEEKS)
        self.assertEqual(trend["calibration"]["buckets"]["route"]["status"], "insufficient")


if __name__ == "__main__":
    unittest.main()
