"""Palier D — dépense énergétique modèle : intégration index/CLI/contrat (#60,
épopée #21, étape 2). Le moteur pur lui-même (`arc_energy.py`) est couvert par
`tests/data/test_arc_energy.py` (étape 1) — ce fichier couvre l'ÉTAPE 2 :

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
  arrondi à 1 décimale des kcal/pourcentages, séance sans `garmin_activity_id`
  (`reason_code="no_garmin_id"`) dans le listing par défaut ;
- contrat `calories_bmr_kcal` (valide, négatif, > calories_kcal).
"""

from __future__ import annotations

import contextlib
import io
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
        (chaîne) à la place de `garmin_activity_id` — ne peut jamais avoir de FIT
        ingéré (`fit-download` dépend de `garminconnect`), voir
        `_energy_reason_for_missing_row`."""
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
        """Le moteur gère la marche (#60) : `walking` doit obtenir une ligne,
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
        """#60, revue de code : un profil imperial peut porter le poids en livres
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
    (revue #60 — une mention « lb » ailleurs dans la puce ne convertit rien)."""

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
        `reason_code="no_garmin_id"`, distinct de `"no_samples"` (elle n'a jamais
        PU avoir de FIT, ce n'est pas un oubli de synchronisation)."""
        self.write_profile_weight(70)
        self.write_activity_no_garmin_id("i123456", day="2026-09-20", calories_kcal=400)
        self.index()
        out = I.energy_report(self.conn)
        self.assertEqual(len(out["sessions"]), 1)
        session = out["sessions"][0]
        self.assertIsNone(session["garmin_activity_id"])
        self.assertEqual(session["reason_code"], "no_garmin_id")
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


# ---------------------------------------------------------------------------
# Try/except SÉPARÉ (#60, revue de code) : GAP/VAM/descente/durabilité d'un
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
            raise RuntimeError("bug injecté par le test (#60)")

        I.G.gap_sample_series = _boom
        try:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.index()
        finally:
            I.G.gap_sample_series = original

        self.assertIn("bug injecté par le test (#60)", stderr.getvalue())
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
            raise RuntimeError("bug injecté par le test (#60), côté énergie")

        I.EN.energy_from_samples = _boom
        try:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.index()
        finally:
            I.EN.energy_from_samples = original

        self.assertIn("bug injecté par le test (#60), côté énergie", stderr.getvalue())
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
            raise RuntimeError("bug injecté par le test (#60)")

        os.environ["ARC_STRICT_METRICS"] = "1"
        I.EN.energy_from_samples = _boom
        try:
            with self.assertRaises(RuntimeError):
                self.index()
        finally:
            I.EN.energy_from_samples = original


# ---------------------------------------------------------------------------
# Contrat : `calories_bmr_kcal` (#60).
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


if __name__ == "__main__":
    unittest.main()
