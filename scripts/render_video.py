#!/usr/bin/env python3
"""Rendu MP4 des vidéos de la série « Le Sentier » (`docs/video/`).

Chaque page dessine chaque image à partir du seul temps écoulé (`render(t)`) et
expose `window.renderFrame(t)`. Ce script l'ouvre dans un Chrome headless,
appelle `renderFrame` image par image — jamais en temps réel, donc aucune image
sautée quelle que soit la machine — et envoie chaque image PNG à ffmpeg. La
narration (`<épisode>/audio/<lang>.m4a`) et les sous-titres (`subs.<lang>.vtt`,
piste désactivable) produits par `scripts/video_narration.py` sont ensuite
ajoutés au MP4 sans réencodage.

Prérequis : `ffmpeg` dans le PATH, `uv`, et Google Chrome ou le Chromium de
Playwright (`uvx playwright install chromium`). Rien n'est installé dans le
projet : Playwright est fourni à la volée par `uv run --with`.

Usage :
    uv run --with playwright scripts/render_video.py                       # bande-annonce
    uv run --with playwright scripts/render_video.py --episode garde-fous --lang en
    uv run --with playwright scripts/render_video.py --episode all --res 1080
    uv run --with playwright scripts/render_video.py --burn-subs           # sous-titres incrustés
    uv run --with playwright scripts/render_video.py --still 42.5          # une image PNG

Sortie par défaut : `dist/video/<épisode>-<lang>-<res>p.mp4` (hors git).
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


VIDEO = DOCS / "video"
LANG_ISO = {"fr": "fra", "en": "eng"}


def all_episodes() -> list[str]:
    """Bande-annonce d'abord, puis les épisodes dans l'ordre de leur dossier (script.json)."""
    eps = sorted(p.parent.name for p in VIDEO.glob("*/script.json"))
    return ["bande-annonce"] + [e for e in eps if e != "bande-annonce"]


def page_of(episode: str) -> str:
    return "video/index.html" if episode == "bande-annonce" else f"video/{episode}/index.html"


def render_episode(pw, port: int, episode: str, args) -> int:
    ep_dir = VIDEO / episode
    suffix = f"-{args.still:g}s.png" if args.still is not None else ".mp4"
    out = args.output or REPO / "dist" / "video" / f"{episode}-{args.lang}-{args.res}p{suffix}"
    out.parent.mkdir(parents=True, exist_ok=True)
    url = (f"http://127.0.0.1:{port}/{page_of(episode)}?capture=1&lang={args.lang}&res={args.res}"
           f"&subs={1 if args.burn_subs else 0}")
    browser = launch_browser(pw)
    try:
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(url)
        page.evaluate("window.videoReady")
        duration = float(page.evaluate("window.DURATION"))
        if not duration:
            print(f"{episode} : durée nulle — narration non générée ? (scripts/video_narration.py)", file=sys.stderr)
            return 1
        if args.still is not None:
            out.write_bytes(grab_png(page, args.still))
            print(out)
            return 0

        end = min(args.end if args.end is not None else duration, duration)
        frames = int(round((end - args.start) * args.fps)) + 1
        silent = out.with_suffix(".video.mp4")
        ffmpeg = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "image2pipe", "-c:v", "png", "-framerate", str(args.fps), "-i", "-",
             "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf), "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(silent)],
            stdin=subprocess.PIPE,
        )
        started = time.monotonic()
        for i in range(frames):
            ffmpeg.stdin.write(grab_png(page, args.start + i / args.fps))
            if i % args.fps == 0 or i == frames - 1:
                print(f"\r{episode} [{args.lang}] {i + 1}/{frames} images", end="", file=sys.stderr, flush=True)
        ffmpeg.stdin.close()
        code = ffmpeg.wait()
        print(f"\n{frames} images en {time.monotonic() - started:.0f} s", file=sys.stderr)
        if code:
            print(f"ffmpeg a échoué (code {code}).", file=sys.stderr)
            return code
    finally:
        browser.close()

    # narration + sous-titres (piste désactivable), sans réencoder l'image
    audio = ep_dir / "audio" / f"{args.lang}.m4a"
    subs = ep_dir / f"subs.{args.lang}.vtt"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent)]
    maps = ["-map", "0:v"]
    if audio.exists() and not args.no_audio:
        cmd += ["-ss", f"{args.start:.3f}", "-i", str(audio)]
        maps += ["-map", "1:a"]
    if subs.exists() and not args.burn_subs and args.start == 0:
        cmd += ["-i", str(subs)]
        maps += ["-map", f"{len(maps) // 2}:s"]
    cmd += maps + ["-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text", "-shortest",
                   "-metadata:s:a:0", f"language={LANG_ISO[args.lang]}",
                   "-metadata:s:s:0", f"language={LANG_ISO[args.lang]}",
                   "-movflags", "+faststart", str(out)]
    code = subprocess.run(cmd).returncode
    silent.unlink(missing_ok=True)
    if code:
        print(f"ffmpeg (multiplexage) a échoué (code {code}).", file=sys.stderr)
        return code
    print(out)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--episode", default="bande-annonce",
                    help="dossier d'épisode sous docs/video/, « bande-annonce » (défaut) ou « all »")
    ap.add_argument("--lang", choices=("fr", "en"), default="fr")
    ap.add_argument("--res", choices=RES_CHOICES, default="1080", help="hauteur de l'image (défaut 1080)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=18, help="qualité x264, plus bas = meilleur (défaut 18)")
    ap.add_argument("--start", type=float, default=0.0, help="début (s)")
    ap.add_argument("--end", type=float, default=None, help="fin (s), défaut : toute la vidéo")
    ap.add_argument("--still", type=float, default=None, help="n'écrit qu'une image PNG à cet instant (s)")
    ap.add_argument("--burn-subs", action="store_true", help="sous-titres incrustés dans l'image (réseaux sociaux)")
    ap.add_argument("--no-audio", action="store_true", help="vidéo muette")
    ap.add_argument("-o", "--output", type=Path, default=None)
    args = ap.parse_args()

    episodes = all_episodes() if args.episode == "all" else [args.episode]
    for ep in episodes:
        if not (VIDEO / page_of(ep).removeprefix("video/")).exists():
            print(f"Épisode inconnu : {ep} (connus : {', '.join(all_episodes())})", file=sys.stderr)
            return 2
    if args.output and len(episodes) > 1:
        print("-o/--output n'a de sens qu'avec un seul épisode.", file=sys.stderr)
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright manquant : uv run --with playwright scripts/render_video.py", file=sys.stderr)
        return 2
    if args.still is None and not shutil.which("ffmpeg"):
        print("ffmpeg introuvable dans le PATH (brew install ffmpeg).", file=sys.stderr)
        return 2

    server, port = serve_docs()
    try:
        with sync_playwright() as pw:
            for ep in episodes:
                code = render_episode(pw, port, ep, args)
                if code:
                    return code
        return 0
    finally:
        server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
