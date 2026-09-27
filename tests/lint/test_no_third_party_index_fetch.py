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
même attendu. Il ne cherche que dans le CODE EXÉCUTABLE (revue de code #62,
élargi au-delà des seuls scripts Python d'origine) :

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
import tempfile
import unittest
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


def scanned_files() -> list:
    """Scripts Python, scripts shell et code de tableau de bord (`web/js`) —
    voir la liste en tête de module. `.git/` exclu explicitement (objets
    internes, jamais du code exécuté)."""
    patterns = [
        (REPO / "scripts").rglob("*.py"),
        (REPO / "skills").rglob("*.py"),
        REPO.rglob("*.sh"),
        (REPO / "web" / "js").rglob("*.js"),
    ]
    files = {p for pattern in patterns for p in pattern if ".git" not in p.parts}
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
