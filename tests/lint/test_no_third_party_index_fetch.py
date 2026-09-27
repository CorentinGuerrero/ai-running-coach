"""Palier B — vie privée #62 : aucun script ne récupère automatiquement l'indice
ITRA/UTMB de l'athlète.

Critère d'acceptation d'#62 : « Aucune récupération automatique de données
personnelles tierces ». Le seul chemin autorisé est un agent qui, À LA DEMANDE
EXPLICITE de l'athlète, utilise son propre outil web (voir `agents/coach.md`) —
jamais un script, une commande shell ou du code de tableau de bord de ce dépôt
qui irait chercher `itra.run`/`utmb.world` de son propre chef à l'indexation,
à la synchronisation ou au chargement du tableau de bord.

Ce test ne cherche PAS ces domaines dans les prompts (`agents/`, `skills/*.md`)
ni dans la documentation (`docs/`) : les CITER en documentation (règle de vie
privée, exemple d'URL à ne jamais appeler automatiquement) est légitime et
même attendu. Il ne cherche que dans le CODE EXÉCUTABLE, parmi les fichiers
SUIVIS PAR GIT (`git ls-files`, revue de code #109 2e tour — jamais un `rglob`
depuis la racine du dépôt, qui descendrait sans le vouloir dans une autre
copie de travail sous `.claude/worktrees/`, ou un `.venv` local, imbriqués
sous la même racine) :

- `scripts/**/*.py`, `skills/**/*.py` — scripts Python du moteur ;
- `**/*.sh` (dont `install.sh` à la racine, `scripts/*.sh`) — scripts shell ;
- `web/js/**/*.js` — code exécuté dans le navigateur par le tableau de bord.

Un fichier qui mentionne ces domaines dans une chaîne de caractères est
presque toujours en train de les appeler (URL, host, endpoint) — le seul autre
cas plausible serait un commentaire, un faux positif que la liste d'exception
ci-dessous couvrirait explicitement, avec justification, au lieu d'affaiblir
le regex.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

FORBIDDEN_DOMAINS = ("itra.run", "utmb.world")
FORBIDDEN_RE = re.compile("|".join(re.escape(d) for d in FORBIDDEN_DOMAINS), re.I)

# Aucune exception aujourd'hui : un futur fichier qui aurait un besoin légitime
# de citer ces domaines (ex. un test verrouillant CE lint) devrait passer par
# cette liste, avec justification en commentaire à côté de l'entrée.
ALLOWLIST = {
    # ce fichier lui-même : il CITE les domaines interdits pour les interdire.
    "tests/lint/test_no_third_party_index_fetch.py",
}


def _tracked_files() -> list:
    """Chemins relatifs suivis par git (`git ls-files`) — jamais un `rglob`
    depuis la racine (revue de code #109, 2e tour) : ce dépôt tourne
    couramment avec d'autres copies de travail sous `.claude/worktrees/`, ou
    un `.venv` local, imbriqués sous la même racine — un `rglob("*.sh")`/
    `rglob("*.py")` non filtré y descendrait et scannerait le contenu d'une
    AUTRE branche (ou d'un environnement virtuel) plutôt que celui de CETTE
    revue. `git ls-files` ne rend que ce que le dépôt suit réellement."""
    proc = subprocess.run(["git", "-C", str(REPO), "ls-files"],
                          capture_output=True, text=True, check=True)
    return proc.stdout.splitlines()


# Sentinelle (revue de code #109, 3e tour) : un fichier dont on SAIT qu'il
# doit toujours faire partie du scan. Sert de garde-fou contre un `git
# ls-files` qui rendrait silencieusement une liste vide ou tronquée (dépôt mal
# reconnu, `GIT_DIR`/`cwd` inattendus, `.git` absent d'une copie extraite) —
# sans cette vérification, `violations([])` passe toujours, même avec
# `itra.run` injecté ailleurs dans le dépôt : un faux sentiment de sécurité
# pire qu'une absence de test.
SENTINEL_FILE = "scripts/arc_index.py"


def scanned_files() -> list:
    """Scripts Python, scripts shell et code de tableau de bord (`web/js`) —
    voir la liste en tête de module — parmi les fichiers suivis par git.

    Échoue bruyamment (au lieu de rendre une liste vide/tronquée en silence)
    si `SENTINEL_FILE`, qui doit TOUJOURS être suivi par git dans ce dépôt,
    n'apparaît pas dans `git ls-files` — signe que la commande n'a pas vu le
    dépôt réel (voir `SENTINEL_FILE`)."""
    tracked = _tracked_files()
    if SENTINEL_FILE not in tracked:
        raise AssertionError(
            f"git ls-files n'a pas rendu {SENTINEL_FILE!r} (dépôt : {REPO}) — la commande ne voit "
            "probablement pas le vrai dépôt git de ce test (GIT_DIR/cwd inattendus, .git absent "
            "d'une copie extraite...). Ce lint ne peut alors RIEN garantir : mieux vaut échouer "
            "bruyamment ici que rendre silencieusement une liste vide de fichiers scannés.")
    files = []
    for rel in tracked:
        is_engine_python = (rel.startswith("scripts/") or rel.startswith("skills/")) and rel.endswith(".py")
        is_shell = rel.endswith(".sh")
        is_dashboard_js = rel.startswith("web/js/") and rel.endswith(".js")
        if is_engine_python or is_shell or is_dashboard_js:
            files.append(REPO / rel)
    return sorted(files)


def violations(files) -> list:
    problems = []
    for path in files:
        rel = path.relative_to(REPO).as_posix()
        if rel in ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if FORBIDDEN_RE.search(text):
            problems.append(rel)
    return problems


class TestNoThirdPartyIndexFetchInScripts(unittest.TestCase):
    def test_no_file_references_itra_or_utmb_domains(self):
        problems = violations(scanned_files())
        self.assertEqual(problems, [],
                          f"fichier(s) référençant itra.run/utmb.world — récupération "
                          f"automatique de données personnelles interdite (#62) : {problems}")


class TestScanGuardsAgainstEmptyGitLsFiles(unittest.TestCase):
    """Revue de code #109, 3e tour, blocker : un `git ls-files` qui rendrait
    silencieusement une liste vide (ou tronquée, sans `SENTINEL_FILE`) ne doit
    JAMAIS laisser `test_no_file_references_itra_or_utmb_domains` passer au
    vert sans avoir rien vérifié — il doit échouer bruyamment à la place."""

    def test_scanned_files_raises_when_sentinel_is_missing(self):
        with unittest.mock.patch(f"{__name__}._tracked_files", return_value=["docs/index.md"]):
            with self.assertRaises(AssertionError):
                scanned_files()

    def test_scanned_files_raises_on_empty_git_ls_files(self):
        with unittest.mock.patch(f"{__name__}._tracked_files", return_value=[]):
            with self.assertRaises(AssertionError):
                scanned_files()


class TestViolationsHelperDetectsInjectedReference(unittest.TestCase):
    """Le test lui-même doit détecter une régression injectée — sans quoi il
    passerait toujours, quel que soit le contenu des fichiers scannés."""

    def test_helper_flags_a_fake_offending_file(self):
        # Répertoire temporaire sous la RACINE du dépôt (jamais sous `scripts/`,
        # revue de code #62 — nit : un fichier orphelin laissé par un crash de
        # test polluerait sinon `scripts/` réel, visible d'un `git status` du
        # contributeur), pour que `path.relative_to(REPO)` (utilisé par
        # `violations()`) reste valide sans toucher aucun dossier réellement
        # scanné. Nettoyé automatiquement en sortie de bloc `with`.
        with tempfile.TemporaryDirectory(dir=REPO) as tmp:
            path = Path(tmp) / "fake_offender.py"
            path.write_text("URL = 'https://itra.run/api/runner/12345'\n", encoding="utf-8")
            self.assertIn(path.relative_to(REPO).as_posix(), violations([path]))


if __name__ == "__main__":
    unittest.main()
