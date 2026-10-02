#!/usr/bin/env python3
"""Narration de la série vidéo « Le Sentier » : script.json -> voix, timing, sous-titres.

Chaque épisode (`docs/video/<dossier>/`) porte un `script.json`, seule source du
découpage et du texte dit :

    {
      "scenes": [
        {"id": "bib", "min": 4.5},
        {"id": "check", "min": 6, "chapter": {"fr": "Le bilan", "en": "The check"},
         "fr": ["Première phrase.", {"text": "Deuxième, pas avant 3 s.", "at": 3.0}],
         "en": ["First sentence.", "Second one."]}
      ]
    }

Pour chaque langue, le script :
  1. synthétise chaque réplique avec Kokoro (ONNX, hors ligne ; FR `ff_siwis`,
     EN `bm_george`), après substitution du lexique de prononciation
     `docs/video/lexicon.json`, complété par `<épisode>/lexicon.json` — les sous-titres gardent le texte d'origine ; une valeur
     `[[…]]` du lexique est une suite de phonèmes IPA passée telle quelle à la voix
     (mots anglais dits « à la française » : trail, /why…) ;
  2. calcule la durée de chaque scène : max(min, attaque + paroles + traîne) ;
  3. écrit `audio/<lang>.m4a` (AAC mono, volume normalisé), `subs.<lang>.vtt`
     et `timing.js` (`window.ARC_TIMING`, lu par docs/video/engine/engine.js).

Les répliques déjà synthétisées sont mises en cache
(`~/.cache/arc-video/tts/<empreinte>.wav`) : relancer ne refait que ce qui a changé.

Prérequis : `ffmpeg`, `uv`, et le modèle Kokoro dans `~/.cache/kokoro-onnx/`
(`kokoro-v1.0.onnx`, `voices-v1.0.bin`, release « model-files-v1.0 » de
github.com/thewh1teagle/kokoro-onnx). Rien n'est installé dans le projet :

    uv run --with kokoro-onnx --with soundfile scripts/video_narration.py            # tous les épisodes
    uv run --with kokoro-onnx --with soundfile scripts/video_narration.py garde-fous --lang fr
    python3 scripts/video_narration.py --check     # stdlib seule : timing.js à jour ?

`--check` (utilisé par le lint du palier B) ne synthétise rien : il vérifie que
chaque `timing.js` correspond au `script.json` courant et que les fichiers audio
existent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VIDEO = REPO / "docs" / "video"
LEXICON = VIDEO / "lexicon.json"
MODEL_DIR = Path.home() / ".cache" / "kokoro-onnx"
CACHE = Path.home() / ".cache" / "arc-video" / "tts"
SR = 24000

VOICES = {
    "fr": {"voice": "ff_siwis", "lang": "fr-fr", "speed": 1.0},
    "en": {"voice": "bm_george", "lang": "en-gb", "speed": 1.0},
}
LEAD, GAP, TAIL = 0.5, 0.35, 0.6


def episodes() -> list[Path]:
    """Dossiers d'épisode : ceux qui portent un script.json."""
    return sorted(p.parent for p in VIDEO.glob("*/script.json"))


def load_script(ep: Path) -> dict:
    data = json.loads((ep / "script.json").read_text(encoding="utf-8"))
    ids = [s["id"] for s in data["scenes"]]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{ep.name}/script.json : identifiants de scène en double")
    return data


def cues_of(scene: dict, lang: str) -> list[dict]:
    out = []
    for c in scene.get(lang, []):
        out.append({"text": c, "at": None} if isinstance(c, str) else {"text": c["text"], "at": c.get("at")})
    return out


def script_digest(ep: Path, data: dict, lang: str) -> str:
    """Empreinte de ce qui détermine le timing d'une langue (texte, minima, voix, lexique)."""
    lex = lexicon(ep, lang)
    payload = {
        "voice": VOICES[lang], "lex": lex, "lead": LEAD, "gap": GAP, "tail": TAIL,
        "scenes": [{"id": s["id"], "min": s.get("min"), "lead": s.get("lead"), "tail": s.get("tail"),
                    "cues": cues_of(s, lang)} for s in data["scenes"]],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def lexicon(ep: Path, lang: str) -> dict:
    """Lexique commun (docs/video/lexicon.json) complété/surchargé par celui de l'épisode."""
    lex = {}
    for f in (LEXICON, ep / "lexicon.json"):
        if f.exists():
            lex.update(json.loads(f.read_text(encoding="utf-8")).get(lang, {}))
    return lex


def pronounce(s: str, lang: str, ep: Path) -> str:
    """Applique le lexique de prononciation (mots entiers, casse exacte)."""
    lex = lexicon(ep, lang)
    for src in sorted(lex, key=len, reverse=True):
        s = re.sub(rf"(?<![\w/]){re.escape(src)}(?!\w)", lex[src], s)
    return s


class Voice:
    """Synthèse Kokoro paresseuse + cache disque des répliques."""

    def __init__(self):
        self._k = None

    def _model(self):
        if self._k is None:
            try:
                from kokoro_onnx import Kokoro
            except ImportError:
                raise SystemExit("kokoro-onnx manquant : uv run --with kokoro-onnx --with soundfile scripts/video_narration.py")
            onnx, voices = MODEL_DIR / "kokoro-v1.0.onnx", MODEL_DIR / "voices-v1.0.bin"
            if not onnx.exists() or not voices.exists():
                raise SystemExit(f"Modèle Kokoro absent de {MODEL_DIR} (voir l'en-tête de ce script).")
            self._k = Kokoro(str(onnx), str(voices))
        return self._k

    def phonemes(self, text: str, lang: str) -> str:
        """Phonèmes espeak SANS drapeaux de changement de langue.

        kokoro-onnx garde les drapeaux par défaut (`(en)kˈoʊtʃ(fr)`) puis ne filtre que
        les parenthèses : la voix française lit alors « en … fr » autour de chaque mot
        anglais (« coach », « slash »). `remove-flags` garde la prononciation anglaise
        du mot, sans les drapeaux."""
        import phonemizer
        from kokoro_onnx.tokenizer import Tokenizer, _espeak_lock
        tok = self._model().tokenizer
        out = []
        # `[[…]]` = phonèmes bruts du lexique, passés tels quels à la voix
        for i, part in enumerate(re.split(r"\[\[(.+?)\]\]", text)):
            if i % 2:
                out.append(part)
            elif part.strip():
                with _espeak_lock:
                    out.append(phonemizer.phonemize(Tokenizer.normalize_text(part), lang, preserve_punctuation=True,
                                                    with_stress=True, language_switch="remove-flags").strip())
            if part[-1:].isspace() or part[:1].isspace():
                out.append(" ")
        ph = re.sub(r"\s+", " ", " ".join(out))
        return "".join(p for p in ph if p in tok.vocab).strip()

    def say(self, text: str, lang: str, ep: Path) -> list[float]:
        v = VOICES[lang]
        spoken = pronounce(text, lang, ep)
        key = hashlib.sha256(json.dumps([spoken, v, "remove-flags", "ipa"], sort_keys=True).encode()).hexdigest()[:24]
        path = CACHE / f"{key}.wav"
        if not path.exists():
            import soundfile as sf
            samples, sr = self._model().create(self.phonemes(spoken, v["lang"]), voice=v["voice"], speed=v["speed"],
                                               lang=v["lang"], is_phonemes=True)
            if sr != SR:
                raise SystemExit(f"Fréquence inattendue {sr} Hz")
            CACHE.mkdir(parents=True, exist_ok=True)
            sf.write(path, samples, SR, subtype="PCM_16")
        return read_wav(path)


def read_wav(path: Path) -> list[int]:
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())
    return list(memoryview(raw).cast("h"))


def write_wav(path: Path, pcm: "array") -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def vtt_time(s: float) -> str:
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{sec:06.3f}"


def build_lang(ep: Path, data: dict, lang: str, voice: Voice) -> dict:
    from array import array
    plan, start, clips = [], 0.0, []
    for sc in data["scenes"]:
        lead = sc.get("lead", LEAD)
        cur, cues = lead, []
        for c in cues_of(sc, lang):
            pcm = voice.say(c["text"], lang, ep)
            if c["at"] is not None:
                cur = max(cur, float(c["at"]))
            dur = len(pcm) / SR
            cues.append({"s": round(cur, 3), "e": round(cur + dur, 3), "text": c["text"]})
            clips.append((start + cur, pcm))
            cur += dur + GAP
        speech_end = (cues[-1]["e"] if cues else 0) + sc.get("tail", TAIL)
        d = round(max(float(sc.get("min", 3.0)), speech_end), 3)
        item = {"id": sc["id"], "start": round(start, 3), "d": d, "cues": cues}
        if sc.get("chapter"):
            item["chapter"] = sc["chapter"][lang] if isinstance(sc["chapter"], dict) else sc["chapter"]
        plan.append(item)
        start += d
    duration = round(start, 3)

    # piste audio complète, alignée sur la timeline
    pcm = array("h", bytes(2 * (int(duration * SR) + SR)))
    for at, clip in clips:
        i0 = int(at * SR)
        for j, v in enumerate(clip):
            if i0 + j < len(pcm):
                pcm[i0 + j] = v
    (ep / "audio").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "voice.wav"
        write_wav(wav, pcm)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-t", f"{duration:.3f}",
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "1",
             "-c:a", "aac", "-b:a", "48k", "-movflags", "+faststart", str(Path(tmp) / f"{lang}.m4a")],
            check=True,
        )
        # remplacement atomique : deux générations simultanées ne corrompent jamais la piste publiée
        shutil.move(str(Path(tmp) / f"{lang}.m4a"), str(ep / "audio" / f"{lang}.m4a"))
    vtt = ["WEBVTT", ""]
    n = 0
    for sc in plan:
        for c in sc["cues"]:
            n += 1
            vtt += [str(n), f"{vtt_time(sc['start'] + c['s'])} --> {vtt_time(sc['start'] + c['e'] + 0.25)}", c["text"], ""]
    (ep / f"subs.{lang}.vtt").write_text("\n".join(vtt), encoding="utf-8")
    return {"digest": script_digest(ep, data, lang), "duration": duration, "scenes": plan}


TIMING_PREFIX = "/* Généré par scripts/video_narration.py — ne pas éditer. */\nwindow.ARC_TIMING = "


def read_timing(ep: Path) -> dict:
    p = ep / "timing.js"
    if not p.exists():
        return {}
    txt = p.read_text(encoding="utf-8")
    body = txt[len(TIMING_PREFIX):].rstrip().rstrip(";") if txt.startswith(TIMING_PREFIX) else "{}"
    return json.loads(body)


def write_timing(ep: Path, timing: dict) -> None:
    (ep / "timing.js").write_text(TIMING_PREFIX + json.dumps(timing, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")


def check(eps: list[Path]) -> int:
    bad = []
    for ep in eps:
        data, timing = load_script(ep), read_timing(ep)
        for lang in VOICES:
            t = timing.get(lang)
            if not t:
                bad.append(f"{ep.name} [{lang}] : timing absent")
            elif t.get("digest") != script_digest(ep, data, lang):
                bad.append(f"{ep.name} [{lang}] : timing périmé (script.json ou lexique modifié)")
            if not (ep / "audio" / f"{lang}.m4a").exists():
                bad.append(f"{ep.name} [{lang}] : audio/{lang}.m4a absent")
    for b in bad:
        print(b, file=sys.stderr)
    if bad:
        print("Régénérer : uv run --with kokoro-onnx --with soundfile scripts/video_narration.py", file=sys.stderr)
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("episodes", nargs="*", help="dossiers d'épisode (défaut : tous)")
    ap.add_argument("--lang", choices=sorted(VOICES), action="append", help="langue (répétable, défaut : toutes)")
    ap.add_argument("--check", action="store_true", help="vérifie seulement que timing.js et l'audio sont à jour")
    args = ap.parse_args(argv)

    known = {p.name: p for p in episodes()}
    for name in args.episodes:
        if name not in known:
            raise SystemExit(f"Épisode inconnu : {name} (connus : {', '.join(sorted(known))})")
    eps = [known[n] for n in args.episodes] if args.episodes else list(known.values())
    if args.check:
        return check(eps)
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg introuvable dans le PATH (brew install ffmpeg).")
    voice = Voice()
    for ep in eps:
        data, timing = load_script(ep), read_timing(ep)
        for lang in args.lang or sorted(VOICES):
            timing[lang] = build_lang(ep, data, lang, voice)
            print(f"{ep.name} [{lang}] {timing[lang]['duration']:.1f} s")
        write_timing(ep, timing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
