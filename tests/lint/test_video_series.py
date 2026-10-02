"""Palier B — la série vidéo « Le Sentier » (docs/video/) reste cohérente.

Aucune synthèse vocale ni navigateur ici : on vérifie seulement ce qui se lit
dans les fichiers versionnés.

- chaque épisode de `SERIES` (docs/video/engine/engine.js) a sa page, son script,
  ses scènes, et `ARC.episode({ n, slug })` y correspond ;
- le minutage (`timing.js`) et l'audio sont à jour du script et du lexique
  (`scripts/video_narration.py --check`) ;
- la galerie `docs/videos.md`, les cartes « En vidéo » et les vignettes sont à jour
  (`scripts/video_gallery.py --check`) ;
- chaque page de documentation visée existe ;
- les scènes sont des fonctions pures du temps : ni `Math.random`, ni `Date.now`,
  ni `new Date(` — sinon l'export image par image ne serait plus reproductible.
"""

from __future__ import annotations

import io
import json
import re
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import video_gallery  # noqa: E402
import video_narration  # noqa: E402

VIDEO = REPO / "docs" / "video"


def episode_dirs() -> list[Path]:
    return [VIDEO / e["dir"] for e in video_gallery.series()]


class TestSeriesStructure(unittest.TestCase):
    def test_every_published_episode_is_complete(self):
        for ep in video_gallery.series():
            d = VIDEO / ep["dir"]
            if not d.exists():
                continue  # épisode annoncé, pas encore tourné
            with self.subTest(episode=ep["dir"]):
                for f in ("script.json", "scenes.js", "timing.js", "poster.jpg", "subs.fr.vtt", "subs.en.vtt",
                          "audio/fr.m4a", "audio/en.m4a"):
                    self.assertTrue((d / f).exists(), f"{d.name}/{f} absent")
                page = VIDEO / ep["page"].removeprefix("video/")
                self.assertTrue(page.exists(), f"page absente : {page}")

    def test_scenes_declare_their_series_number_and_slug(self):
        for ep in video_gallery.series():
            js = VIDEO / ep["dir"] / "scenes.js"
            if not js.exists():
                continue
            src = js.read_text(encoding="utf-8")
            with self.subTest(episode=ep["dir"]):
                m = re.search(r"ARC\.episode\(\{\s*n:\s*(\d+),\s*slug:\s*\"([^\"]+)\"", src)
                self.assertIsNotNone(m, "appel ARC.episode({ n, slug, … }) introuvable")
                self.assertEqual(int(m.group(1)), ep["n"])
                self.assertEqual(m.group(2), ep["dir"])

    def test_scripts_open_on_the_bib_and_close_on_the_finish_line(self):
        for d in episode_dirs():
            if d.name == "bande-annonce" or not (d / "script.json").exists():
                continue
            ids = [s["id"] for s in json.loads((d / "script.json").read_text(encoding="utf-8"))["scenes"]]
            with self.subTest(episode=d.name):
                self.assertEqual(ids[0], "bib")
                self.assertEqual(ids[-1], "finish")

    def test_every_scene_has_both_languages_or_neither(self):
        for d in episode_dirs():
            if not (d / "script.json").exists():
                continue
            for sc in json.loads((d / "script.json").read_text(encoding="utf-8"))["scenes"]:
                with self.subTest(episode=d.name, scene=sc["id"]):
                    self.assertEqual(bool(sc.get("fr")), bool(sc.get("en")), "réplique dans une seule langue")
                    if sc.get("chapter"):
                        self.assertEqual(set(sc["chapter"]), {"fr", "en"})

    def test_scenes_are_pure_functions_of_time(self):
        for d in episode_dirs():
            js = d / "scenes.js"
            if not js.exists():
                continue
            src = js.read_text(encoding="utf-8")
            with self.subTest(episode=d.name):
                for bad in ("Math.random", "Date.now", "new Date(", "performance.now"):
                    self.assertNotIn(bad, src, f"{d.name}/scenes.js : {bad} rend le rendu non reproductible")

    def test_documentation_targets_exist(self):
        docs = REPO / "docs"
        for ep in video_gallery.series():
            if not ep["docs"]:
                continue
            with self.subTest(episode=ep["dir"]):
                stem = docs / ep["docs"].rstrip("/")
                self.assertTrue(stem.with_suffix(".md").exists() or (stem / "index.md").exists(),
                                f"page de documentation absente : {ep['docs']}")


class TestGeneratedFilesAreFresh(unittest.TestCase):
    def test_narration_timing_matches_scripts(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = video_narration.main(["--check"])
        self.assertEqual(code, 0, err.getvalue())

    def test_gallery_cards_and_posters_are_up_to_date(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = video_gallery.main(["--check"])
        self.assertEqual(code, 0, err.getvalue())

    def test_lexicons_are_valid(self):
        for f in [VIDEO / "lexicon.json", *VIDEO.glob("*/lexicon.json")]:
            with self.subTest(file=f.name):
                data = json.loads(f.read_text(encoding="utf-8"))
                for lang in ("fr", "en"):
                    self.assertIsInstance(data.get(lang, {}), dict)


if __name__ == "__main__":
    unittest.main()
