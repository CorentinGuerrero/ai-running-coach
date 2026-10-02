#!/usr/bin/env python3
"""Galerie de la série vidéo « Le Sentier » dans la documentation MkDocs.

Source unique : `SERIES` dans `docs/video/engine/engine.js` (ordre, titres, page de
documentation associée), plus, par épisode, `script.json` (`summary`, `poster`) et
`timing.js` (durées réelles, générées par `scripts/video_narration.py`).

Le script remplit deux sortes de blocs balisés, sans toucher au reste du fichier :

- `docs/videos.md`, entre `<!-- arc-videos:start -->` et `<!-- arc-videos:end -->` :
  la grille de toutes les vidéos ;
- n'importe quelle page `docs/**/*.md`, entre `<!-- arc-video:<dossier> -->` et
  `<!-- /arc-video -->` : la carte « En vidéo » d'un épisode (chemins relatifs
  calculés selon la profondeur de la page).

    python3 scripts/video_gallery.py            # régénère les blocs
    python3 scripts/video_gallery.py --check    # échoue si un bloc est périmé (palier B)
    uv run --with playwright scripts/video_gallery.py --posters   # + vignettes poster.jpg

Les vignettes (`docs/video/<dossier>/poster.jpg`) sont rendues depuis la page de
l'épisode, à l'instant `poster` de son script.json (défaut : le dossard, recadré
autour de lui ; `poster_crop` = [x, y, l, h] en px de l'image 1280×720 pour choisir).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
VIDEO = DOCS / "video"
ENGINE = VIDEO / "engine" / "engine.js"
GALLERY = DOCS / "videos.md"
START, END = "<!-- arc-videos:start -->", "<!-- arc-videos:end -->"
CARD_RE = re.compile(r"(<!-- arc-video:([a-z0-9-]+) -->)(.*?)(<!-- /arc-video -->)", re.S)
DEFAULT_POSTER_S = 2.8
BIB_CROP = [216, 104, 848, 477]  # px de l'image 1280×720 (rendu ?res=720)


def series() -> list[dict]:
    """Lit SERIES dans engine.js (une entrée par ligne : { n, dir, docs, fr, en })."""
    src = ENGINE.read_text(encoding="utf-8")
    body = src[src.index("const SERIES = ["):]
    body = body[: body.index("];")]
    out = []
    for m in re.finditer(r'\{ n: (\d+), dir: "([^"]*)", docs: "([^"]*)", fr: "([^"]*)", en: "([^"]*)" \}', body):
        n, d, docs, fr, en = m.groups()
        out.append({"n": int(n), "dir": d or "bande-annonce", "page": f"video/{d}/index.html" if d else "video/index.html",
                    "docs": docs, "fr": fr, "en": en})
    if not out:
        raise SystemExit("SERIES introuvable dans engine.js")
    return out


def timing(ep: dict) -> dict:
    p = VIDEO / ep["dir"] / "timing.js"
    if not p.exists():
        return {}
    txt = p.read_text(encoding="utf-8")
    return json.loads(txt[txt.index("=") + 1:].strip().rstrip(";"))


def script(ep: dict) -> dict:
    p = VIDEO / ep["dir"] / "script.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def dur(seconds: float) -> str:
    s = round(seconds)
    return f"{s // 60} min {s % 60:02d}" if s >= 60 else f"{s} s"


def available(ep: dict) -> bool:
    return (VIDEO / ep["dir"] / "timing.js").exists()


def num(ep: dict) -> str:
    return "Bande-annonce" if ep["n"] == 0 else f"Étape {ep['n']:02d}"


def gallery_block(eps: list[dict]) -> str:
    rows = ["<div class=\"arc-videos\" markdown>", ""]
    for ep in eps:
        if not available(ep):
            continue
        t, sc = timing(ep), script(ep)
        page = ep["page"]
        summary = (sc.get("summary") or {}).get("fr", "")
        en = t.get("en", {}).get("duration")
        rows += [
            f"<div class=\"arc-video{' arc-video--featured' if ep['n'] == 0 else ''}\" markdown>",
            "",
            f"[![{ep['fr']}](video/{ep['dir']}/poster.jpg)]({page})",
            "",
            f"<span class=\"arc-video__meta\">{num(ep)} · {dur(t['fr']['duration'])}</span>",
            "",
            f"### [{ep['fr']}]({page})",
            "",
            summary,
            "",
            f"[Regarder]({page}) · [English{f' ({dur(en)})' if en else ''}]({page}?lang=en)"
            + (f" · [La documentation]({ep['docs']}index.md)" if ep["docs"] and (DOCS / ep["docs"]).is_dir()
               else f" · [La documentation]({ep['docs'].rstrip('/')}.md)" if ep["docs"] else ""),
            "",
            "</div>",
            "",
        ]
    rows.append("</div>")
    return "\n".join(rows)


def card_block(ep: dict, md: Path) -> str:
    rel = "../" * (len(md.relative_to(DOCS).parts) - 1)
    t, sc = timing(ep), script(ep)
    page = f"{rel}{ep['page']}"
    summary = (sc.get("summary") or {}).get("fr", "")
    return "\n".join([
        "",
        "<div class=\"arc-video-card\" markdown>",
        "",
        f"[![{ep['fr']}]({rel}video/{ep['dir']}/poster.jpg)]({page})",
        "",
        "<div markdown>",
        "",
        f"<span class=\"arc-video__meta\">En vidéo · {num(ep)} · {dur(t['fr']['duration'])}</span>",
        "",
        f"**[{ep['fr']}]({page})** — {summary}",
        "",
        f"[Regarder]({page}) · [English]({page}?lang=en) · [Toutes les vidéos]({rel}videos.md)",
        "",
        "</div>",
        "",
        "</div>",
        "",
    ])


def render_all() -> dict[Path, str]:
    """Contenu attendu de chaque fichier touché (seulement ceux qui changent)."""
    eps = series()
    by_dir = {e["dir"]: e for e in eps}
    changed = {}
    if GALLERY.exists():
        src = GALLERY.read_text(encoding="utf-8")
        if START in src and END in src:
            new = src[: src.index(START) + len(START)] + "\n" + gallery_block(eps) + "\n" + src[src.index(END):]
            if new != src:
                changed[GALLERY] = new
    for md in sorted(DOCS.rglob("*.md")):
        src = changed.get(md) or md.read_text(encoding="utf-8")
        if "<!-- arc-video:" not in src:
            continue

        def fill(m):
            ep = by_dir.get(m.group(2))
            if not ep:
                raise SystemExit(f"{md.relative_to(REPO)} : épisode inconnu « {m.group(2)} »")
            body = card_block(ep, md) if available(ep) else "\n"
            return m.group(1) + body + m.group(4)

        new = CARD_RE.sub(fill, src)
        if new != src:
            changed[md] = new
    return changed


def posters(eps: list[dict]) -> None:
    import base64
    import functools
    import http.server
    import threading
    from playwright.sync_api import sync_playwright

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):  # noqa: D401 - silence du journal d'accès
            pass

    handler = functools.partial(Quiet, directory=str(DOCS))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(channel="chrome")
            except Exception:  # noqa: BLE001 - repli sur le Chromium de Playwright
                browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            for ep in eps:
                if not available(ep):
                    continue
                sc = script(ep)
                at = float(sc.get("poster", DEFAULT_POSTER_S))
                # sur le dossard (défaut), on recadre autour de lui : le numéro reste lisible en vignette
                crop = sc.get("poster_crop", BIB_CROP if "poster" not in sc else [0, 0, 1280, 720])
                page.goto(f"http://127.0.0.1:{server.server_address[1]}/{ep['page']}?capture=1&lang=fr&res=720")
                page.evaluate("window.videoReady")
                data = page.evaluate(
                    """([t, r]) => { window.renderFrame(t); const c = document.getElementById('c');
                       const o = document.createElement('canvas'); o.width = 768; o.height = 432;
                       o.getContext('2d').drawImage(c, r[0], r[1], r[2], r[3], 0, 0, 768, 432);
                       return o.toDataURL('image/jpeg', 0.82); }""", [at, crop])
                out = VIDEO / ep["dir"] / "poster.jpg"
                out.write_bytes(base64.b64decode(data.split(",", 1)[1]))
                print(out.relative_to(REPO))
            browser.close()
    finally:
        server.shutdown()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="échoue si un bloc ou une vignette est périmé·e")
    ap.add_argument("--posters", action="store_true", help="rend aussi les vignettes (Playwright)")
    args = ap.parse_args(argv)
    eps = series()
    if args.check:
        bad = [f"{p.relative_to(REPO)} : bloc vidéo périmé" for p in render_all()]
        bad += [f"docs/video/{e['dir']}/poster.jpg absent" for e in eps
                if available(e) and not (VIDEO / e["dir"] / "poster.jpg").exists()]
        for b in bad:
            print(b, file=sys.stderr)
        if bad:
            print("Régénérer : uv run --with playwright scripts/video_gallery.py --posters", file=sys.stderr)
        return 1 if bad else 0
    if args.posters:
        posters(eps)
    for path, content in render_all().items():
        path.write_text(content, encoding="utf-8")
        print(path.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
