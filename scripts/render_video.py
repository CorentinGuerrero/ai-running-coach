#!/usr/bin/env python3
"""Rendu MP4 de la présentation animée (`docs/video/index.html`).

La page dessine chaque image à partir du seul temps écoulé (`render(t)`) et
expose `window.renderFrame(t)`. Ce script l'ouvre dans un Chrome headless,
appelle `renderFrame` image par image — jamais en temps réel, donc aucune image
sautée quelle que soit la machine — et envoie chaque image PNG à ffmpeg.

Prérequis : `ffmpeg` dans le PATH, `uv`, et Google Chrome ou le Chromium de
Playwright (`uvx playwright install chromium`). Rien n'est installé dans le
projet : Playwright est fourni à la volée par `uv run --with`.

Usage :
    uv run --with playwright scripts/render_video.py
    uv run --with playwright scripts/render_video.py --lang en --res 2160 --fps 60
    uv run --with playwright scripts/render_video.py --still 42.5   # une image PNG

Sortie par défaut : `dist/video/ai-running-coach-<lang>-<res>p.mp4` (hors git).
Les polices sont servies depuis `docs/video/fonts/` par un serveur HTTP local
(127.0.0.1, port éphémère) : aucune requête vers un service tiers.
"""

from __future__ import annotations

import argparse
import base64
import functools
import http.server
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
RES_CHOICES = ("720", "1080", "1440", "2160")


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D401 - silence du journal d'accès
        pass


def serve_docs() -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(_QuietHandler, directory=str(DOCS))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def launch_browser(pw):
    """Chrome installé d'abord, sinon le Chromium de Playwright."""
    try:
        return pw.chromium.launch(channel="chrome")
    except Exception:  # noqa: BLE001 - repli explicite, l'erreur finale suffit
        return pw.chromium.launch()


def grab_png(page, t: float) -> bytes:
    data_url = page.evaluate(
        "t => { window.renderFrame(t); return document.getElementById('c').toDataURL('image/png'); }", t
    )
    return base64.b64decode(data_url.split(",", 1)[1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lang", choices=("fr", "en"), default="fr")
    ap.add_argument("--res", choices=RES_CHOICES, default="1080", help="hauteur de l'image (défaut 1080)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=18, help="qualité x264, plus bas = meilleur (défaut 18)")
    ap.add_argument("--start", type=float, default=0.0, help="début (s)")
    ap.add_argument("--end", type=float, default=None, help="fin (s), défaut : toute la vidéo")
    ap.add_argument("--still", type=float, default=None, help="n'écrit qu'une image PNG à cet instant (s)")
    ap.add_argument("-o", "--output", type=Path, default=None)
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright manquant : uv run --with playwright scripts/render_video.py", file=sys.stderr)
        return 2
    if args.still is None and not shutil.which("ffmpeg"):
        print("ffmpeg introuvable dans le PATH (brew install ffmpeg).", file=sys.stderr)
        return 2

    suffix = f"-{args.still:g}s.png" if args.still is not None else ".mp4"
    out = args.output or REPO / "dist" / "video" / f"ai-running-coach-{args.lang}-{args.res}p{suffix}"
    out.parent.mkdir(parents=True, exist_ok=True)

    server, port = serve_docs()
    url = f"http://127.0.0.1:{port}/video/index.html?capture=1&lang={args.lang}&res={args.res}"
    try:
        with sync_playwright() as pw:
            browser = launch_browser(pw)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url)
            page.evaluate("window.videoReady")
            duration = float(page.evaluate("window.DURATION"))

            if args.still is not None:
                out.write_bytes(grab_png(page, args.still))
                print(out)
                return 0

            end = min(args.end if args.end is not None else duration, duration)
            frames = int(round((end - args.start) * args.fps)) + 1
            ffmpeg = subprocess.Popen(
                ["ffmpeg", "-y", "-loglevel", "error",
                 "-f", "image2pipe", "-c:v", "png", "-framerate", str(args.fps), "-i", "-",
                 "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf), "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", str(out)],
                stdin=subprocess.PIPE,
            )
            started = time.monotonic()
            for i in range(frames):
                ffmpeg.stdin.write(grab_png(page, args.start + i / args.fps))
                if i % args.fps == 0 or i == frames - 1:
                    print(f"\r{i + 1}/{frames} images", end="", file=sys.stderr, flush=True)
            ffmpeg.stdin.close()
            code = ffmpeg.wait()
            browser.close()
            print(f"\n{frames} images en {time.monotonic() - started:.0f} s", file=sys.stderr)
            if code:
                print(f"ffmpeg a échoué (code {code}).", file=sys.stderr)
                return code
            print(out)
            return 0
    finally:
        server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
