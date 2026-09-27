"""Palier B — vie privée #62 : aucun script ne récupère automatiquement l'indice
ITRA/UTMB de l'athlète.

Critère d'acceptation d'#62 : « Aucune récupération automatique de données
personnelles tierces ». Le seul chemin autorisé est un agent qui, À LA DEMANDE
EXPLICITE de l'athlète, utilise son propre outil web (voir `agents/coach.md`) —
jamais un script de ce dépôt qui irait chercher `itra.run`/`utmb.world` de son
propre chef à l'indexation ou à la synchronisation.

Ce test ne cherche PAS ces domaines dans les prompts (`agents/`, `skills/*.md`) :
les CITER en documentation (règle de vie privée, exemple d'URL à ne jamais
appeler automatiquement) est légitime et même attendu. Il ne cherche que dans
le CODE exécutable (`scripts/**/*.py`, `skills/**/scripts/*.py`) : un script qui
mentionne ces domaines dans une chaîne de caractères est presque toujours en
train de les appeler (URL, host, endpoint) — le seul autre cas plausible serait
un commentaire, un faux positif que la liste d'exception ci-dessous couvrirait
explicitement, avec justification, au lieu d'affaiblir le regex.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

FORBIDDEN_DOMAINS = ("itra.run", "utmb.world")
FORBIDDEN_RE = re.compile("|".join(re.escape(d) for d in FORBIDDEN_DOMAINS), re.I)

# Aucune exception aujourd'hui : un futur script qui aurait un besoin légitime de
# citer ces domaines (ex. un test verrouillant CE lint) devrait passer par cette
# liste, avec justification en commentaire à côté de l'entrée.
ALLOWLIST = {
    # ce fichier lui-même : il CITE les domaines interdits pour les interdire.
    "tests/lint/test_no_third_party_index_fetch.py",
}


def python_files() -> list:
    files = list((REPO / "scripts").rglob("*.py"))
    files += list((REPO / "skills").rglob("*.py"))
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
    def test_no_script_references_itra_or_utmb_domains(self):
        problems = violations(python_files())
        self.assertEqual(problems, [],
                          f"script(s) référençant itra.run/utmb.world — récupération "
                          f"automatique de données personnelles interdite (#62) : {problems}")


class TestViolationsHelperDetectsInjectedReference(unittest.TestCase):
    """Le test lui-même doit détecter une régression injectée — sans quoi il
    passerait toujours, quel que soit le contenu de `scripts/`/`skills/`."""

    def test_helper_flags_a_fake_offending_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, dir=REPO / "scripts") as fh:
            fh.write("URL = 'https://itra.run/api/runner/12345'\n")
            path = Path(fh.name)
        try:
            self.assertIn(path.relative_to(REPO).as_posix(), violations([path]))
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
