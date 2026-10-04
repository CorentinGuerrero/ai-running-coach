"""Palier D — coefficient de technicité du terrain par section (#186, épopée #170).

Familles : table tags -> coefficient, pondération montée/descente, appariement au plus proche
chemin (Overpass simulé, aucun réseau), déclaration (fichier), cache disque, hors ligne,
composition avec la nuit, cohérence des scénarios, sortie octet pour octet sans technicité.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import arc_race_pacing as RP  # noqa: E402
import arc_technicity as T  # noqa: E402
from tests.data.test_arc_race_night import (  # noqa: E402
    GOLDEN_NO_NIGHT_SHA256, RACE_DATE, TZ, _golden_kwargs, _kwargs, _ultra_pts,
)
from tests.data.test_arc_race_pacing import PERSONAL_BINS  # noqa: E402


def _way(way_id, pts, km_from, km_to, tags):
    """Chemin OSM fictif suivant la trace entre `km_from` et `km_to` (format Overpass `out tags geom`)."""
    d = T.cumulative_m(pts)
    geom = [{"lat": p["lat"], "lon": p["lon"]} for p, x in zip(pts, d) if km_from * 1000 <= x <= km_to * 1000]
    return {"type": "way", "id": way_id, "tags": tags, "geometry": geom}


class TestTagTable(unittest.TestCase):
    def test_sac_scale_ladder_is_monotonic(self):
        values = [T.coef_from_tags({"sac_scale": k})[0] for k in T.SAC_SCALE_EXCESS]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[0], 1.0)
        self.assertAlmostEqual(T.coef_from_tags({"sac_scale": "alpine_hiking"})[0], 1.30)

    def test_dominant_plus_half_second(self):
        coef, used = T.coef_from_tags({"sac_scale": "demanding_mountain_hiking", "surface": "rock"})
        self.assertAlmostEqual(coef, 1.0 + 0.15 + 0.5 * 0.12)
        self.assertIn("sac_scale=demanding_mountain_hiking", used)

    def test_missing_or_unknown_tags_never_invent(self):
        self.assertEqual(T.coef_from_tags({}), (1.0, []))
        self.assertEqual(T.coef_from_tags({"surface": "lunar_regolith", "name": "x"}), (1.0, []))

    def test_never_below_one_and_capped(self):
        self.assertGreaterEqual(T.coef_from_tags({"surface": "asphalt"})[0], 1.0)
        worst = {"sac_scale": "difficult_alpine_hiking", "trail_visibility": "no", "surface": "sand",
                 "tracktype": "grade5", "highway": "steps"}
        self.assertLessEqual(T.coef_from_tags(worst)[0], T.COEF_MAX)

    def test_grade_weight_downhill_weighs_more(self):
        self.assertEqual(T.grade_weight(None), 1.0)
        self.assertEqual(T.grade_weight(0.0), 1.0)
        self.assertEqual(T.grade_weight(8.0), T.UPHILL_WEIGHT)
        self.assertLess(T.grade_weight(8.0), T.grade_weight(0.0))
        self.assertGreater(T.grade_weight(-8.0), 1.0)
        self.assertEqual(T.grade_weight(-30.0), T.DOWNHILL_WEIGHT_MAX)
        self.assertAlmostEqual(T.effective_factor(1.2, -30.0), 1.3)
        self.assertAlmostEqual(T.effective_factor(1.2, 10.0), 1.14)


class TestMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pts = _ultra_pts()

    def _ways(self, *specs):
        return T.parse_ways({"elements": [_way(s[0], self.pts, s[1], s[2], s[3]) for s in specs]})

    def test_parse_ways_ignores_nodes_and_empty_geometry(self):
        payload = {"elements": [{"type": "node", "id": 1, "lat": -40.0, "lon": -140.0},
                                {"type": "way", "id": 2, "tags": {}, "geometry": []},
                                _way(3, self.pts, 0, 1, {"highway": "path"})]}
        ways = T.parse_ways(payload)
        self.assertEqual([w["id"] for w in ways], [3])

    def test_nearest_way_within_radius_only(self):
        ways = self._ways((1, 0, 10, {"highway": "path", "sac_scale": "alpine_hiking"}))
        p = self.pts[40]
        self.assertIsNotNone(T.nearest_way(p["lat"], p["lon"], ways))
        off = T.nearest_way(p["lat"] + 0.001, p["lon"], ways)  # ~111 m
        self.assertIsNone(off)

    def test_nearest_way_picks_closest(self):
        a = {"id": 1, "tags": {"highway": "track"}, "geom": [(-40.0, -140.0), (-40.0, -139.99)]}
        b = {"id": 2, "tags": {"highway": "path"}, "geom": [(-40.00005, -140.0), (-40.00005, -139.99)]}  # ~5.6 m
        got = T.nearest_way(-40.00003, -139.995, [a, b])
        self.assertEqual(got["id"], 2)

    def test_section_coefficients_from_stub(self):
        ways = self._ways((1, 0, 30, {"highway": "path", "sac_scale": "alpine_hiking"}),
                          (2, 30, 91, {"highway": "track", "tracktype": "grade1", "surface": "asphalt"}))
        segs = RP.segment_course(self.pts, target_segment_m=750.0)
        coefs = T.section_coefficients(segs, self.pts, ways=ways)
        first, last = coefs[2], coefs[-3]
        self.assertEqual(first["source"], "osm")
        self.assertAlmostEqual(first["coef"], 1.31, places=2)
        self.assertIn("sac_scale=alpine_hiking", first["tags"])
        self.assertAlmostEqual(last["coef"], 1.0, places=2)
        self.assertGreater(first["coverage_pct"], 90)

    def test_sparse_coverage_gives_no_coefficient(self):
        ways = self._ways((1, 0, 1, {"highway": "path", "sac_scale": "alpine_hiking"}))
        segs = RP.segment_course(self.pts, target_segment_m=750.0)
        coefs = T.section_coefficients(segs, self.pts, ways=ways)
        self.assertEqual(coefs[20]["source"], "none")
        self.assertEqual(coefs[20]["coef"], 1.0)


class TestDeclared(unittest.TestCase):
    def test_validation(self):
        for bad in ({"sections": []}, {"sections": [{"km_start": 5, "km_end": 2, "coef": 1.1}]},
                    {"sections": [{"km_start": 0, "km_end": 2, "coef": 3.0}]},
                    {"sections": [{"km_start": 0, "km_end": 2}]}, "x"):
            with self.assertRaises(T.TechnicityError):
                T.validate_declared(bad)
        self.assertEqual(T.validate_declared({"sections": [{"km_start": 0, "km_end": 2, "coef": 0.9}]})[0]["coef"], 0.9)

    def test_load_declared_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "t.json"
            f.write_text(json.dumps({"sections": [{"km_start": 0, "km_end": 5, "coef": 1.25, "note": "pierrier"}]}))
            self.assertEqual(T.load_declared(f)[0]["note"], "pierrier")
            with self.assertRaises(T.TechnicityError):
                T.load_declared(Path(d) / "absent.json")
            f.write_text("{pas du json")
            with self.assertRaises(T.TechnicityError):
                T.load_declared(f)

    def test_declared_wins_over_osm(self):
        pts = _ultra_pts()
        ways = T.parse_ways({"elements": [_way(1, pts, 0, 91, {"highway": "path", "sac_scale": "alpine_hiking"})]})
        segs = RP.segment_course(pts, target_segment_m=750.0)
        declared = [{"km_start": 0.0, "km_end": 10.0, "coef": 1.1, "note": ""}]
        coefs = T.section_coefficients(segs, pts, declared=declared, ways=ways)
        self.assertEqual(coefs[0]["source"], "declared")
        self.assertEqual(coefs[0]["coef"], 1.1)
        self.assertEqual(coefs[-1]["source"], "osm")


class TestFetchAndCache(unittest.TestCase):
    def test_chunked_requests_dedup_and_cache(self):
        pts = _ultra_pts()
        calls = []
        way = _way(7, pts, 0, 91, {"highway": "path"})

        def fetcher(q):
            calls.append(q)
            return {"elements": [way]}

        with tempfile.TemporaryDirectory() as d:
            ways, info = T.fetch_ways(pts, cache_dir=Path(d), fetcher=fetcher, sleep=lambda _s: None)
            self.assertGreater(len(calls), 5)  # 90 km / 8 km
            self.assertEqual(len(ways), 1)  # dédoublonné entre tronçons
            self.assertEqual(info["requests"], len(calls))
            n = len(calls)
            ways2, info2 = T.fetch_ways(pts, cache_dir=Path(d), fetcher=fetcher, sleep=lambda _s: None)
            self.assertEqual(len(calls), n)  # tout vient du cache
            self.assertEqual(info2["cache_hits"], info["chunks"])
            self.assertEqual(len(ways2), 1)

    def test_query_shape(self):
        q = T.build_query((45.1, 6.1, 45.2, 6.2))
        self.assertIn("out tags geom", q)
        self.assertIn("(45.1,6.1,45.2,6.2)", q)

    def test_offline_raises_overpass_error(self):
        def boom(_q):
            raise T.OverpassError("réseau coupé")
        with self.assertRaises(T.OverpassError):
            T.fetch_ways(_ultra_pts(), fetcher=boom, sleep=lambda _s: None)

    def test_only_rounded_bbox_in_query(self):
        pts = _ultra_pts()
        q = T.build_query(T.chunk_bboxes(T.sample_track(pts))[0])
        self.assertNotIn("ele", q)


class TestPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pts = _ultra_pts()
        cls.ways = T.parse_ways({"elements": [
            _way(1, cls.pts, 0, 91, {"highway": "path", "sac_scale": "demanding_mountain_hiking"})]})
        cls.base = RP.build_race_plan(cls.pts, PERSONAL_BINS, start_time="16:00", tz=TZ, **_kwargs())
        cls.tech = RP.build_race_plan(
            cls.pts, PERSONAL_BINS, start_time="16:00", tz=TZ, **_kwargs(),
            technicity={"declared": None, "ways": cls.ways, "osm_requested": True, "osm_status": "ok",
                        "osm_note": None, "osm_info": {"requests": 1, "cache_hits": 0}})

    def test_slower_everywhere_with_osm_coefficient(self):
        for s in RP.SCENARIOS:
            self.assertGreater(self.tech["totals"]["time_s"][s], self.base["totals"]["time_s"][s])

    def test_plan_and_section_objects(self):
        info = self.tech["technicity"]
        self.assertEqual(info["status"], "applied")
        self.assertEqual(info["osm"]["status"], "ok")
        self.assertGreater(info["mean_coef"], 1.1)
        self.assertEqual(info["distance_pct_by_source"]["osm"], 100.0)
        for seg in self.tech["segments"]:
            self.assertEqual(set(seg["technicity"]), {"coef", "effective_factor", "source", "tags", "coverage_pct"})
        self.assertNotIn("technicity", self.base)
        self.assertNotIn("technicity", self.base["segments"][0])

    def test_scenario_order_preserved_per_section(self):
        for seg in self.tech["segments"]:
            t = seg["predicted_time_s"]
            self.assertGreaterEqual(t["safe"], t["realistic"])
            self.assertGreaterEqual(t["realistic"], t["ambitious"])

    def test_descent_penalised_more_than_climb(self):
        down = [s for s in self.tech["segments"] if (s["grade_mean_pct"] or 0) < -2.5]
        up = [s for s in self.tech["segments"] if (s["grade_mean_pct"] or 0) > 2.5]
        self.assertTrue(down and up)
        self.assertGreater(down[0]["technicity"]["effective_factor"], up[0]["technicity"]["effective_factor"])

    def test_composes_with_night(self):
        self.assertEqual(self.tech["night"]["status"], "night")
        self.assertGreater(self.base["night"]["scenarios"]["realistic"]["night_duration_s"], 0)
        # plus lent -> plus longtemps dans la nuit : la durée de nuit ne peut pas diminuer
        self.assertGreaterEqual(self.tech["night"]["scenarios"]["realistic"]["night_duration_s"],
                                self.base["night"]["scenarios"]["realistic"]["night_duration_s"])
        seg = next(s for s in self.tech["segments"] if s["night_fraction"]["realistic"] > 0)
        self.assertIn("technicity", seg)

    def test_declared_only_changes_declared_section(self):
        decl = [{"km_start": 0.0, "km_end": 20.0, "coef": 1.25, "note": "pierrier"}]
        plan = RP.build_race_plan(self.pts, PERSONAL_BINS, **_kwargs(),
                                  technicity={"declared": decl, "ways": None, "osm_requested": False})
        base = RP.build_race_plan(self.pts, PERSONAL_BINS, **_kwargs())
        flat = [s for s in plan["segments"] if s["km_start"] >= 35 and s["km_end"] <= 55][0]
        ref = next(s for s in base["segments"] if s["id"] == flat["id"])
        self.assertEqual(flat["predicted_time_s"], ref["predicted_time_s"])
        self.assertEqual(flat["technicity"]["source"], "none")
        self.assertEqual(plan["segments"][0]["technicity"]["source"], "declared")
        self.assertEqual(plan["technicity"]["sources_requested"], ["declared"])

    def test_offline_gives_note_and_unchanged_times(self):
        plan = RP.build_race_plan(
            self.pts, PERSONAL_BINS, **_kwargs(),
            technicity={"declared": None, "ways": None, "osm_requested": True, "osm_status": "unavailable",
                        "osm_note": "OpenStreetMap indisponible (x)", "osm_info": None})
        base = RP.build_race_plan(self.pts, PERSONAL_BINS, **_kwargs())
        self.assertEqual(plan["technicity"]["status"], "no_coefficient")
        self.assertEqual(plan["totals"], base["totals"])
        self.assertTrue(any("indisponible" in w for w in plan["warnings"]))

    def test_assumptions_document_the_model(self):
        text = RP.ASSUMPTIONS["technicity"]
        for needle in ("APPROXIMATIONS DU PROJET", "sac_scale", "trail_visibility", "surface", "Overpass",
                       "MATCH_RADIUS_M", "identique", "débrief"):
            self.assertIn(needle, text)


class TestByteIdenticalWithoutTechnicity(unittest.TestCase):
    def test_default_plan_matches_pre_186_fingerprint(self):
        plan = RP.build_race_plan(_ultra_pts(), PERSONAL_BINS, **_golden_kwargs())
        self.assertNotIn("technicity", plan)
        plan.pop("assumptions")
        plan.pop("night")
        text = json.dumps(plan, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), GOLDEN_NO_NIGHT_SHA256)

    def test_explicit_none_equals_omitted(self):
        a = RP.build_race_plan(_ultra_pts(), PERSONAL_BINS, **_golden_kwargs())
        b = RP.build_race_plan(_ultra_pts(), PERSONAL_BINS, technicity=None, **_golden_kwargs())
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


class TestResolver(unittest.TestCase):
    def test_none_when_absent(self):
        self.assertIsNone(RP._resolve_technicity(None, [], Path(".")))

    def test_offline_osm_is_not_fatal(self):
        orig = T.fetch_ways

        def boom(*_a, **_k):
            raise T.OverpassError("dns")
        T.fetch_ways = boom
        try:
            with tempfile.TemporaryDirectory() as d:
                out = RP._resolve_technicity(["osm"], _ultra_pts(), Path(d))
        finally:
            T.fetch_ways = orig
        self.assertEqual(out["osm_status"], "unavailable")
        self.assertIn("aucun coefficient", out["osm_note"])
        self.assertIsNone(out["ways"])

    def test_declared_file_and_osm_cache_dir(self):
        orig = T.fetch_ways
        seen = {}

        def fake(pts, cache_dir=None, **_k):
            seen["dir"] = cache_dir
            return [], {"requests": 0, "cache_hits": 0, "chunks": 0}
        T.fetch_ways = fake
        try:
            with tempfile.TemporaryDirectory() as d:
                f = Path(d) / "t.json"
                f.write_text(json.dumps({"sections": [{"km_start": 0, "km_end": 5, "coef": 1.2}]}))
                out = RP._resolve_technicity([str(f), "osm"], _ultra_pts(), Path(d))
                self.assertEqual(seen["dir"], Path(d) / ".arc" / "overpass")
        finally:
            T.fetch_ways = orig
        self.assertEqual(out["declared"][0]["coef"], 1.2)
        self.assertEqual(out["osm_status"], "ok")


if __name__ == "__main__":
    unittest.main()
