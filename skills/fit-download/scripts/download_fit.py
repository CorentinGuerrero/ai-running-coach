#!/usr/bin/env python3
"""Téléchargeur de fichiers FIT Garmin — bypass du canal MCP.

Résout le timeout MCP de `get_activity_fit_data` (records GPS = payload
de plusieurs Mo qui dépasse le timeout côté client). Ce script utilise la
librairie `garminconnect` déjà installée dans l'environnement `garmin-mcp` et
les tokens locaux `~/.garminconnect` — aucun mot de passe nécessaire.

Usage:
  download_fit.py 12345678901                          # -> activities/12345678901.fit
  download_fit.py 12345678901 --json                   # + JSON des records GPS
  download_fit.py 12345678901 12345678902 12345678903  # plusieurs
  download_fit.py --from-dir activities/               # lit activity_id dans les MD
  download_fit.py 12345678901 --output-dir /tmp/fits/

Options:
  --output-dir   Répertoire de sortie (défaut: activities/)
  --json         Écrit aussi <id>.records.json (bruts fitparse) ET la copie normalisée
                 activities/fit/<id>.json (#42 — ingérée par `scripts/arc_index.py`)
  --overwrite    Ré-télécharge même si le fichier existe
  --refresh-dynamics
                 (#151) RÉ-EXTRAIT la dynamique de course (temps de contact, balance, oscillation et
                 ratio verticaux, longueur de pas) depuis les `.fit` DÉJÀ présents dans le répertoire
                 de sortie, vers `activities/fit/<id>.json`. Aucun téléchargement, aucune connexion
                 Garmin : nécessite seulement `fitparse` (relance avec le python de garmin-mcp).
                 N'écrit que ces JSON dérivés (jetables, jamais versionnés) — jamais un Markdown, jamais
                 un `.fit`. Idempotent : un JSON déjà à jour est laissé tel quel. Ensuite, relancer
                 `scripts/arc_index.py` (ou ouvrir le tableau de bord) réingère les fichiers changés.
  --dry-run      Avec `--refresh-dynamics` : liste (id par id) ce qui serait créé / réécrit, sans rien écrire
  -v, --verbose  Avec `--refresh-dynamics` : liste aussi les id déjà à jour
                 Un `.fit` téléchargé sans `--json` n'a pas de JSON normalisé : `--refresh-dynamics` le CRÉE.
  --python PATH  Interpréteur contenant garminconnect (auto-détecté sinon)

Sans `--overwrite`, une séance déjà téléchargée est sautée — avec `--json`, ce
saut porte sur la copie NORMALISÉE canonique (`<out_dir>/fit/<id>.json`), pas
sur le seul `.fit` brut (voir `_should_skip_download`) : relancer cette commande
avec `--from-dir --json` sur un historique déjà rattrapé ne re-télécharge donc
que les séances qui n'ont pas encore leur copie normalisée.

Avec `--json`, en plus du dump brut `fitparse` (`<id>.records.json`, à des fins de
diagnostic/analyse fine — `skills/session-parts-analyzer`), une copie **normalisée**
est écrite au chemin canonique `activities/fit/<id>.json` (voir `scripts/arc_samples.py`
pour le format et les règles de normalisation — unités, doublement de la cadence
course à pied). C'est ce second fichier que `scripts/arc_index.py` ingère dans
`activity_sample` ; le premier (`<id>.records.json`) reste inchangé pour compatibilité
ascendante avec les skills qui le lisent déjà (`session-parts-analyzer`).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# skills/<skill>/scripts/download_fit.py → 3 niveaux jusqu'à la racine du MOTEUR (là où
# vivent scripts/coach_setup.py et scripts/arc_samples.py) — jamais celle du workspace,
# voir `_activity_dir_out` ci-dessous pour la distinction et le bug qu'elle corrige.
_ENGINE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ENGINE_ROOT / "scripts"))


def _activity_dir_out() -> Path:
    """Répertoire par défaut : `activities/` du WORKSPACE (pas forcément le moteur).

    Bug corrigé (revue PR #87) : une version antérieure remontait depuis `__file__`
    (`skills/<skill>/scripts/download_fit.py` → 3 niveaux) pour dériver `activities/`.
    Correct uniquement quand moteur et workspace sont le même dossier (installation
    fusionnée) — dans une installation séparée (`--workspace`, `docs/workspace.md`),
    `skills/` du workspace est un LIEN SYMBOLIQUE vers le moteur, que `Path.resolve()`
    suit : le résultat pointait alors TOUJOURS `<moteur>/activities`, jamais le
    workspace réel de l'utilisateur — les échantillons canoniques n'étaient donc
    jamais là où `scripts/arc_index.py` (qui, lui, résout bien le workspace via
    `coach_setup.workspace_root`) les cherche.

    Même résolution que `scripts/coach_setup.workspace_root()` : `$ARC_WORKSPACE`,
    puis le pointeur `~/.config/ai-running-coach/workspace`, puis (installation
    fusionnée ou pointeur absent) le moteur lui-même — la même chaîne que le reste
    du projet (`scripts/lib/config.sh`, `arc_index.py`).
    """
    from coach_setup import workspace_root  # noqa: E402 (sys.path déjà préparé plus haut)

    return workspace_root() / "activities"


def relaunch_candidates(garmin_python=None, garmin_mcp_exe=None, home=None) -> list[str]:
    """Interpréteurs candidats (ordre de priorité) : `GARMIN_PYTHON`, le venv du binaire `garmin-mcp` du PATH, puis
    l'emplacement uv par défaut. `python3` ET `python` à chaque fois (sur Linux l'un est un lien vers l'autre)."""
    candidates: list[str] = []
    if garmin_python:
        candidates.append(os.path.expanduser(garmin_python))
    if garmin_mcp_exe:
        bindir = os.path.dirname(os.path.realpath(garmin_mcp_exe))
        candidates += [os.path.join(bindir, n) for n in ("python3", "python")]
    base = os.path.join(home or os.path.expanduser("~"), ".local/share/uv/tools/garmin-mcp/bin")
    candidates += [os.path.join(base, n) for n in ("python3", "python")]
    return candidates


def is_current_interpreter(candidate: str, prefix: str = None, executable: str = None) -> bool:
    """Le candidat est-il l'interpréteur courant ? Un venv se reconnaît à son dossier (`pyvenv.cfg` à côté de
    `bin/`), PAS au `realpath` de son python : sur Linux `bin/python` d'un venv uv est un lien vers
    `/usr/bin/python3.x`, donc identique au python système une fois résolu — alors que les deux n'ont pas les
    mêmes paquets. Sans `pyvenv.cfg`, repli sur la comparaison des chemins résolus."""
    prefix = prefix or sys.prefix
    executable = executable or sys.executable
    venv_dir = os.path.dirname(os.path.dirname(os.path.abspath(candidate)))
    if os.path.isfile(os.path.join(venv_dir, "pyvenv.cfg")):
        return os.path.realpath(venv_dir) == os.path.realpath(prefix)
    return os.path.realpath(candidate) == os.path.realpath(executable)


def pick_relaunch_candidate(candidates, prefix: str = None, executable: str = None) -> str | None:
    for py in candidates:
        if os.path.exists(py) and not is_current_interpreter(py, prefix, executable):
            return py
    return None


def _auto_relaunch(argv: list[str], module: str = "garminconnect") -> None:
    """Relance ce script avec le python de garmin-mcp si `module` est absent (`garminconnect` pour
    un téléchargement ; `fitparse` suffit pour `--refresh-dynamics`, sans connexion Garmin)."""
    try:
        __import__(module)
        return
    except ImportError:
        pass

    # Ordre : --python (via GARMIN_PYTHON), garmin-mcp du PATH, puis l'emplacement uv
    # par défaut — ~/.local/bin est souvent absent du PATH d'une session SSH/cron.
    py = pick_relaunch_candidate(relaunch_candidates(os.environ.get("GARMIN_PYTHON"), shutil.which("garmin-mcp")))
    if py:
        r = subprocess.run([py, os.path.abspath(__file__)] + argv)
        sys.exit(r.returncode)

    print(
        f"ERREUR : module '{module}' introuvable dans cet interpréteur.\n"
        "→ utilisez le python de garmin-mcp : --python ~/.local/share/uv/tools/garmin-mcp/bin/python3",
        file=sys.stderr,
    )
    sys.exit(2)


def _login(client, token_dir: str) -> None:
    """Authentifie avec les tokens locaux (même store que le MCP garmin)."""
    try:
        client.login(token_dir)
    except TypeError:
        client.login()


def _unwrap_fit(data: bytes) -> bytes:
    """Garmin renvoie parfois un ZIP contenant le .fit → dézippe à la volée."""
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            inner = next((n for n in z.namelist() if n.lower().endswith(".fit")), None)
            if inner:
                return z.read(inner)
    return data


def _ensure_gitignore(directory: Path, header: str, patterns: list[str]) -> None:
    """Garantit que chaque motif de `patterns` figure dans `directory/.gitignore`.

    Fichier absent : créé avec `header` + les motifs. Fichier déjà présent (ex. un
    `.gitignore` que l'athlète a lui-même écrit dans `activities/`) : le contenu
    existant n'est JAMAIS écrasé (whatever l'utilisateur y a mis — même geste que
    `.arc/.gitignore` dans `arc_index.open_db`), mais les motifs qui y manquent
    ENCORE sont ajoutés à la suite. Bug corrigé (revue PR #87) : une version
    antérieure de cette fonction ne faisait rien dès que le fichier existait, même
    sans les motifs attendus — un `.gitignore` préexistant dans `activities/` (créé
    par l'installateur, ou par l'athlète pour tout autre motif) empêchait alors
    silencieusement l'exclusion de `*.fit`/`*.records.json`, et le `git add -A` de
    `daily-sync` aurait committé des pistes GPS complètes dans le dépôt privé.
    Idempotent : un motif déjà présent (créé par un appel précédent, ou par
    l'utilisateur) n'est jamais dupliqué.
    """
    marker = directory / ".gitignore"
    if not marker.is_file():
        marker.write_text(header + "\n".join(patterns) + "\n", encoding="utf-8")
        return
    existing_text = marker.read_text(encoding="utf-8")
    existing_lines = {line.strip() for line in existing_text.splitlines()}
    missing = [p for p in patterns if p not in existing_lines]
    if not missing:
        return
    # Racine propre avant d'ajouter : un fichier existant sans retour à la ligne final
    # ne doit pas coller le premier motif ajouté à la dernière ligne existante.
    prefix = "" if not existing_text or existing_text.endswith("\n") else "\n"
    marker.write_text(existing_text + prefix + "\n".join(missing) + "\n", encoding="utf-8")


def _download_one(client, activity_id: int, out_dir: Path, want_json: bool) -> Path:
    from garminconnect import Garmin

    fit = client.download_activity(activity_id, dl_fmt=Garmin.ActivityDownloadFormat.ORIGINAL)
    fit = _unwrap_fit(fit)

    # FIT brut + records.json (pistes GPS complètes) : lourds, jetables, jamais
    # versionnés — même dans un workspace privé qui versionne `activities/`
    # (docs/workspace.md). `daily-sync` avec `git_autocommit = true` fait un
    # `git add -A` : sans ce marqueur, ces fichiers y seraient embarqués (should-fix
    # #4, revue PR #87). Motifs `*.fit`/`*.records.json` CIBLÉS, jamais un `*` : ce
    # répertoire (`out_dir`, normalement `activities/` du workspace) contient aussi
    # les Markdown de séances, versionnés eux — un blanket-ignore les exclurait à
    # tort du dépôt.
    _ensure_gitignore(out_dir, "# FIT bruts + records GPS complets : lourds, jetables, jamais versionnés.\n",
                       ["*.fit", "*.records.json"])

    out = out_dir / f"{activity_id}.fit"
    out.write_bytes(fit)
    print(f"OK {len(fit):,} octets -> {out}")

    if want_json and fit:
        records, sport = _write_records_json(fit, out.with_suffix(".records.json"))
        _write_canonical_samples(activity_id, records, out_dir, sport)
    return out


def _read_fit(fit: bytes) -> tuple[list[dict], str | None]:
    """Records FIT bruts (champs `fitparse` tels quels, valeurs nulles/binaires écartées) et sport
    de la séance (message `session`, minuscules) — sans rien écrire. Partagé par l'écriture du
    dump brut et par `--refresh-dynamics`."""
    import fitparse

    f = fitparse.FitFile(io.BytesIO(fit))
    records: list[dict] = []
    for m in f.get_messages("record"):
        r: dict = {}
        for field in m.fields:
            if field.value is None or isinstance(field.value, bytes):
                continue
            r[field.name] = field.value
        records.append(r)

    sport = None
    for m in f.get_messages("session"):
        value = m.get_value("sport")
        if value is not None:
            sport = str(value).lower()
            break
    return records, sport


def refresh_dynamics(out_dir: Path, dry_run: bool = False) -> dict:
    """Ré-extrait la copie normalisée `<out_dir>/fit/<id>.json` de chaque `<out_dir>/<id>.fit` présent
    (#151) — pour rattraper la dynamique de course sur les FIT déjà téléchargés avant qu'elle soit
    extraite. Ne touche QUE ces JSON dérivés (pas de Markdown, pas de `.fit`, pas de réseau) ; les
    clés du JSON existant autres que `records` sont conservées. Idempotent : contenu identique =
    fichier laissé intact. Un `.fit` téléchargé SANS `--json` n'a pas encore de JSON : il est CRÉÉ (`created`),
    pas seulement réécrit. Rend des compteurs `{"created", "rewritten", "unchanged", "failed", "with_dynamics",
    "files": [(id, statut)]}` ; `dry_run` compte sans écrire."""
    import arc_samples as S  # noqa: E402 (sys.path déjà préparé en tête de module)

    fit_dir = out_dir / "fit"
    result: dict = {"created": 0, "rewritten": 0, "unchanged": 0, "failed": 0, "with_dynamics": 0, "files": []}
    for fit_path in sorted(out_dir.glob("*.fit")):
        if not fit_path.stem.isdigit():
            continue
        activity_id = int(fit_path.stem)
        try:
            records, sport = _read_fit(fit_path.read_bytes())
            normalised = S.normalise_records(records, sport=sport)
        except Exception as e:  # noqa: BLE001 — un FIT illisible ne doit pas arrêter le lot
            print(f"FAIL {activity_id}: {e}", file=sys.stderr)
            result["failed"] += 1
            result["files"].append((activity_id, "failed"))
            continue
        if any(rec.get(k) is not None for rec in normalised for k in S.DYNAMICS_KEYS):
            result["with_dynamics"] += 1
        target = fit_dir / f"{activity_id}.json"
        payload: dict = {}
        if target.is_file():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    payload = existing
            except (ValueError, OSError):
                payload = {}
        payload.update({"activity_id": activity_id, "records": normalised})
        text = json.dumps(payload, ensure_ascii=False)
        if target.is_file() and target.read_text(encoding="utf-8") == text:
            result["unchanged"] += 1
            result["files"].append((activity_id, "unchanged"))
            continue
        existed = target.is_file()       # sinon : `.fit` téléchargé sans `--json`, le JSON est CRÉÉ
        if not dry_run:
            fit_dir.mkdir(parents=True, exist_ok=True)
            _ensure_gitignore(fit_dir, "# Échantillons FIT normalisés : jetables, jamais versionnés.\n",
                               ["*", "!.gitignore"])
            target.write_text(text, encoding="utf-8")
        key = "rewritten" if existed else "created"
        result[key] += 1
        result["files"].append((activity_id, ("would_" if dry_run else "") + {"rewritten": "rewrite", "created": "create"}[key]
                                 if dry_run else key))
    return result


def _write_records_json(fit: bytes, out: Path) -> tuple[list[dict], str | None]:
    """Extrait les records (timestamp, lat/long, altitude, FC, cadence, power) → JSON
    BRUT (champs `fitparse` tels quels), et le sport de la séance (message FIT
    `session`, ex. `"running"`, `"cycling"`). Rend `(records, sport)` pour
    `_write_canonical_samples`, qui les normalise (#42) sans reparser le FIT une
    seconde fois — `sport` gouverne le doublement (ou non) de la cadence, spécifique
    aux sports à pied (voir `arc_samples.CADENCE_DOUBLING_SPORTS` — un FIT vélo lu
    sans ce paramètre verrait sa cadence, déjà complète, doublée à tort)."""
    records, sport = _read_fit(fit)

    out.write_text(json.dumps(records, default=str))
    print(f"OK {len(records)} records -> {out} (sport: {sport or 'inconnu'})")
    return records, sport


def _write_canonical_samples(activity_id: int, raw_records: list[dict], activities_root: Path,
                              sport: str | None = None) -> None:
    """Copie normalisée (#42) au chemin canonique `activities/fit/<id>.json`, ingérée par
    `scripts/arc_index.py` (table `activity_sample`). `activities_root` est le
    `--output-dir` de ce script — normalement `activities/` du workspace ; si un autre
    répertoire est passé, la copie canonique reste relative à CE répertoire (pas au
    workspace) pour ne jamais écrire hors de l'endroit demandé par l'utilisateur.

    `scripts/arc_samples.py` est un module stdlib pur (pas de dépendance à
    `garminconnect`/`fitparse`) : l'importer ici ne casse pas la contrainte « aucune
    dépendance dans l'index » (CONTRIBUTING.md) — seul CE script (déjà hors-stdlib pour
    `garminconnect`/`fitparse`) l'utilise en plus de `arc_index.py`. `sport` (lu du
    message FIT `session` par `_write_records_json`) gouverne le doublement de la
    cadence course à pied — voir `arc_samples.normalise_records`.
    """
    import arc_samples as S  # noqa: E402 (sys.path déjà préparé en tête de module)

    fit_dir = activities_root / "fit"
    fit_dir.mkdir(parents=True, exist_ok=True)
    _ensure_gitignore(fit_dir, "# Échantillons FIT normalisés : jetables, jamais versionnés.\n",
                       ["*", "!.gitignore"])
    records = S.normalise_records(raw_records, sport=sport)
    out = fit_dir / f"{activity_id}.json"
    out.write_text(json.dumps({"activity_id": activity_id, "records": records}, ensure_ascii=False),
                    encoding="utf-8")
    print(f"OK {len(records)} échantillons normalisés -> {out}")


def _activity_id_from_arc(text: str):
    """`garmin_activity_id` du bloc ```arc (contrat workspace-data-contract), ou None."""
    m = re.search(r"^```arc[ \t]*\n(.*?)\n```", text, re.M | re.S)
    if not m:
        return None
    try:
        value = json.loads(m.group(1)).get("garmin_activity_id")
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, int) else None


def _should_skip_download(dst: Path, out_dir: Path, activity_id: int, *,
                           overwrite: bool, want_json: bool) -> bool:
    """`True` si `activity_id` peut être sauté (déjà téléchargé) — jamais un simple
    `dst.exists()` (le `.fit` brut) quand `--json` est demandé : une version
    antérieure re-téléchargeait ALORS SYSTÉMATIQUEMENT chaque séance déjà présente
    dès que `--json` était passé (revue de code, correctif rattrapage historique) —
    coûteux et inutile sur un historique de centaines de séances déjà rattrapées.
    Avec `--json`, on saute aussi UNIQUEMENT si la copie **normalisée** canonique
    (`<out_dir>/fit/<activity_id>.json`, celle qu'`arc_index.py` ingère réellement,
    voir `_write_canonical_samples`) existe déjà — le `.fit` brut seul ne suffit pas
    (une exécution antérieure SANS `--json` n'a jamais produit cette copie).
    Avec `--json`, la copie normalisée suffit : si l'athlète a supprimé les `.fit`
    bruts (lourds, jetables) en gardant `fit/<id>.json`, rien n'est re-téléchargé.
    `overwrite=True` ne saute jamais, quel que soit l'état des fichiers."""
    if overwrite:
        return False
    if want_json:
        return (out_dir / "fit" / f"{activity_id}.json").exists()
    return dst.exists()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Télécharge des fichiers FIT Garmin (bypass MCP) via garminconnect + tokens locaux."
    )
    ap.add_argument("activity_ids", nargs="*", type=int, help="IDs Garmin à télécharger")
    ap.add_argument("--output-dir", type=Path, default=None, help="Répertoire de sortie (défaut: activities/)")
    ap.add_argument("--json", action="store_true", help="Écrit aussi <id>.records.json")
    ap.add_argument("--overwrite", action="store_true", help="Réécrire même si présent")
    ap.add_argument("--from-dir", type=Path, default=None, help="Scan de fichiers MD pour activity_id")
    ap.add_argument("--python", type=Path, default=None, help="Interpréteur garminconnect (override)")
    ap.add_argument("--refresh-dynamics", action="store_true",
                    help="Ré-extrait la dynamique de course des .fit déjà présents (aucun téléchargement)")
    ap.add_argument("--dry-run", action="store_true", help="Avec --refresh-dynamics : n'écrit rien")
    ap.add_argument("-v", "--verbose", action="store_true", help="Avec --refresh-dynamics : liste aussi les id à jour")
    args = ap.parse_args(argv)

    if args.python:
        os.environ["GARMIN_PYTHON"] = str(args.python)
    if args.refresh_dynamics:
        # Hors ligne : ni `garminconnect` ni tokens — seul `fitparse` est requis.
        _auto_relaunch(sys.argv[1:], "fitparse")
        out_dir = args.output_dir or _activity_dir_out()
        result = refresh_dynamics(out_dir, dry_run=args.dry_run)
        labels = {"create": "à créer", "rewrite": "à réécrire", "created": "créé", "rewritten": "réécrit",
                  "unchanged": "déjà à jour", "failed": "échec"}
        for activity_id, status in result["files"]:
            if status != "unchanged" or args.verbose:
                print(f"  {activity_id} : {labels.get(status.replace('would_', ''), status)}")
        if args.dry_run:
            print(f"{result['created']} JSON à créer, {result['rewritten']} à réécrire, ", end="")
        else:
            print(f"{result['created']} JSON créés, {result['rewritten']} réécrits, ", end="")
        print(f"{result['unchanged']} déjà à jour, {result['failed']} échec(s) ; "
              f"{result['with_dynamics']} séance(s) avec dynamique de course — {out_dir / 'fit'}")
        return 1 if result["failed"] else 0
    _auto_relaunch(sys.argv[1:])

    ids: list[int] = list(args.activity_ids)
    if args.from_dir:
        for md in args.from_dir.glob("*.md"):
            txt = md.read_text(encoding="utf-8", errors="ignore")
            found = _activity_id_from_arc(txt)
            if found is None:
                # Fichiers antérieurs au contrat : la clé en début de ligne du bloc YAML
                # uniquement — un « activity_id: 123 » cité dans la prose n'est pas une séance.
                m = re.search(r"^activity_id:\s*(\d+)", txt, re.M)
                found = int(m.group(1)) if m else None
            if found is not None:
                ids.append(found)
        ids = sorted(set(ids))
    if not ids:
        ap.error("aucun activity_id fourni (args ou --from-dir)")

    out_dir = args.output_dir or _activity_dir_out()
    out_dir.mkdir(parents=True, exist_ok=True)

    token_dir = str(Path("~/.garminconnect").expanduser())
    from garminconnect import Garmin

    client = Garmin()
    _login(client, token_dir)

    ok = 0
    for aid in ids:
        dst = out_dir / f"{aid}.fit"
        if _should_skip_download(dst, out_dir, aid, overwrite=args.overwrite, want_json=args.json):
            print(f"skip {aid} (existe) — --overwrite pour forcer")
            continue
        try:
            _download_one(client, aid, out_dir, args.json)
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {aid}: {e}", file=sys.stderr)
    print(f"{ok}/{len(ids)} téléchargements OK dans {out_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())