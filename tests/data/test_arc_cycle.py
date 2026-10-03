"""Palier D — contexte du cycle menstruel opt-in (#166) : `scripts/arc_cycle.py`, contrat `arc`
(`cycle_phase`/`cycle_day`/`cycle_source`), index et saisie manuelle `/log`.

Aucune donnée réelle : toutes les valeurs sont synthétiques.
"""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import arc_contract as C  # noqa: E402
import arc_cycle as CY  # noqa: E402
import arc_index as I  # noqa: E402
import arc_log as L  # noqa: E402


def _mode(config):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        return CY.cycle_tracking_mode(config), err.getvalue()


class TestConfigParsing(unittest.TestCase):
    def test_default_is_off_without_warning(self):
        for config in ({}, {"health": {}}, {"health": {"cycle_tracking": ""}}):
            mode, err = _mode(config)
            self.assertEqual((mode, err), ("off", ""))

    def test_valid_values_are_case_and_space_insensitive(self):
        for raw, expected in (("garmin", "garmin"), (" Manual ", "manual"), ("INTERVALS", "intervals")):
            self.assertEqual(_mode({"health": {"cycle_tracking": raw}})[0], expected)

    def test_invalid_values_fall_back_to_off_with_a_warning_never_raise(self):
        for raw in ("oui", "true", True, 3, ["garmin"]):
            mode, err = _mode({"health": {"cycle_tracking": raw}})
            self.assertEqual(mode, "off")
            self.assertIn("avertissement", err)

    def test_settings_exposes_the_resolved_mode(self):
        self.assertEqual(I.settings({})["cycle_tracking"], "off")
        self.assertEqual(I.settings({"health": {"cycle_tracking": "manual"}})["cycle_tracking"], "manual")

    def test_effective_source_follows_data_source(self):
        self.assertEqual(CY.effective_source("off", "garmin"), "off")
        self.assertEqual(CY.effective_source("garmin", "garmin"), "garmin")
        self.assertEqual(CY.effective_source("garmin", "intervals"), "manual")
        self.assertEqual(CY.effective_source("intervals", "intervals"), "intervals")
        self.assertEqual(CY.effective_source("manual", "garmin"), "manual")


class TestNormalization(unittest.TestCase):
    def test_phase_aliases(self):
        cases = {"luteal": "luteal", "Lutéale": "luteal", "phase lutéale": "luteal",
                 "FOLLICULAR": "follicular", "folliculaire": "follicular",
                 "ovulation": "ovulation", "règles": "menstrual", "MENSTRUAL": "menstrual"}
        for raw, expected in cases.items():
            self.assertEqual(CY.normalize_phase(raw), expected, raw)

    def test_unknown_phase_is_none_never_guessed(self):
        for raw in ("", "n/a", "PREGNANT", None, 3):
            self.assertIsNone(CY.normalize_phase(raw))

    def test_day(self):
        self.assertEqual(CY.normalize_day("J21"), 21)
        self.assertEqual(CY.normalize_day(" 14 "), 14)
        self.assertEqual(CY.normalize_day(22.0), 22)
        for raw in (0, 61, -3, "abc", True, None, 2.5):
            self.assertIsNone(CY.normalize_day(raw), raw)

    def test_gap_days(self):
        out = CY.gap_days("2026-06-01", "2026-09-10")
        self.assertEqual(out["days_since_last_period"], 101)
        self.assertTrue(out["consult_suggested"])
        self.assertFalse(CY.gap_days("2026-09-01", "2026-09-10")["consult_suggested"])
        self.assertTrue(CY.gap_days("2026-06-13", "2026-09-10")["consult_suggested"] is False)
        with self.assertRaises(ValueError):
            CY.gap_days("2026-09-11", "2026-09-10")


HEALTH = {"arc": 1, "kind": "health", "date": "2026-09-23", "morning_check": "full",
          "cycle_phase": "luteal", "cycle_day": 22, "cycle_source": "manual"}


class TestContract(unittest.TestCase):
    def _validate(self, data):
        errors, _warnings = C.validate(data)
        return errors

    def test_valid_cycle_keys(self):
        self.assertEqual(self._validate(dict(HEALTH)), [])

    def test_invalid_values_rejected(self):
        for key, value in (("cycle_phase", "pregnant"), ("cycle_day", 0), ("cycle_day", 61),
                           ("cycle_day", "21"), ("cycle_source", "oura")):
            bad = dict(HEALTH, **{key: value})
            self.assertTrue(self._validate(bad), (key, value))

    def test_keys_are_optional(self):
        bare = {k: v for k, v in HEALTH.items() if not k.startswith("cycle_")}
        self.assertEqual(self._validate(bare), [])


class TestLogManualEntry(unittest.TestCase):
    def test_off_ignores_the_entry_and_writes_nothing(self):
        out = L.process({"cycle": {"phase": "lutéale", "day": "21"}, "cycle_tracking": "off"})
        self.assertEqual(out["cycle"], {"ignored": "tracking_off"})
        self.assertNotIn("health_merge", out)
        self.assertTrue(any("off" in w for w in out["warnings"]))

    def test_manual_normalizes_and_merges(self):
        out = L.process({"cycle": {"phase": "lutéale", "day": "J21"}, "cycle_tracking": "manual"})
        self.assertEqual(out["health_merge"],
                         {"cycle_source": "manual", "cycle_phase": "luteal", "cycle_day": 21})

    def test_unreadable_value_goes_to_unknown(self):
        out = L.process({"cycle": {"phase": "bof", "day": "21"}, "cycle_tracking": "manual"})
        self.assertEqual([u["field"] for u in out["cycle"]["unknown"]], ["phase"])
        self.assertEqual(out["health_merge"], {"cycle_source": "manual", "cycle_day": 21})

    def test_duplicate_does_not_merge(self):
        out = L.process({"cycle": {"phase": "luteal"}, "cycle_tracking": "garmin",
                         "raw_text": "phase lutéale", "existing_log_entries": ["[/log 2026-09-23T08:00:00+00:00] phase lutéale"]})
        self.assertTrue(out["duplicate"])
        self.assertNotIn("health_merge", out)

    def test_without_cycle_key_nothing_changes(self):
        out = L.process({"rpe": "7"})
        self.assertNotIn("cycle", out)
        self.assertNotIn("health_merge", out)

    def test_config_driven_default_is_off(self):
        import tempfile
        with tempfile.TemporaryDirectory() as ws:
            out = L.process({"cycle": {"phase": "luteal"}}, workspace=Path(ws))
        self.assertEqual(out["cycle"], {"ignored": "tracking_off"})


class TestIndexColumns(unittest.TestCase):
    def test_health_day_has_cycle_columns_and_schema_bumped(self):
        self.assertGreaterEqual(I.SCHEMA_VERSION, 33)
        for col in ("cycle_phase", "cycle_day", "cycle_source"):
            self.assertIn(col, I.DDL)


if __name__ == "__main__":
    unittest.main()
