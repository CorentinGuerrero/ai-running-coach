"""Palier B — libellés du modèle Runner_Profile inchangés (#62).

`templates/Runner_Profile.template.md` est lu par `arc_legacy.parse_profile` :
un libellé (`- **Libellé** :`) qui change de forme casse silencieusement la
lecture de tout profil déjà rempli par un athlète — c'est exactement la classe
de bug que le palier B existe pour attraper (voir l'en-tête de
`test_prompt_lint.py`).

**Le vrai garde-fou est `TestParseProfileLabelsExistInTemplate`, pas
`PRE_EXISTING_LABELS`** (revue de code #62). Un instantané hardcodé dans CE
fichier de test n'offre aucune protection réelle contre un renommage : un
contributeur qui renomme un libellé du modèle ET met à jour la liste dans la
même PR ferait passer le test sans que rien n'ait réellement été vérifié
d'indépendant. `TestParseProfileLabelsExistInTemplate` évite ce défaut en ne
comparant le modèle à AUCUNE copie figée : elle extrait, par lecture directe du
code source, les libellés que `arc_legacy.parse_profile` lit réellement via
`_pick(b, ...)`, et vérifie que CHACUN résout contre le modèle ACTUEL (via
`arc_legacy._pick` lui-même — même règle d'égalité/préfixe qu'à l'exécution).
Renommer un libellé sans mettre le parseur à jour (ou l'inverse) échoue
immédiatement ; les deux ensemble ne peuvent pas passer « par accident »
puisqu'aucune valeur n'est recopiée nulle part.

`PRE_EXISTING_LABELS` reste en complément (pas un instantané de sécurité, un
répertoire de non-régression VISIBLE dans un diff) : elle fige la liste et
l'ordre relatif des libellés connus avant #62, pour qu'une revue de code voie
immédiatement dans le diff de PR si l'un d'eux disparaît ou change de place —
un signal humain utile en plus du vrai garde-fou ci-dessus, jamais un
remplacement.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import arc_legacy as L  # noqa: E402

TEMPLATE = REPO / "templates" / "Runner_Profile.template.md"
ARC_LEGACY = REPO / "scripts" / "arc_legacy.py"

# Libellé de premier niveau, gras, suivi de « : » — que la valeur qui suit soit
# vide (modèle) ou remplie (profil réel d'un athlète) : c'est délibérément plus
# permissif que `arc_legacy.parse_bullets` (qui ignore une valeur vide), pour
# pouvoir vérifier la présence des libellés du MODÈLE lui-même, où chaque champ
# est par construction laissé vide.
_TOP_LABEL_RE = re.compile(r"^[-*]\s+\*\*([^*]+)\*\*\s*:")

PRE_EXISTING_LABELS = [
    "Prénom / surnom", "Année de naissance", "Années de pratique",
    "Disponibilité hebdomadaire", "Jours impossibles", "Contraintes de vie",
    "FC max", "FC de repos de référence", "FC au seuil", "Sexe",
    "Zones / seuils", "Allures de référence", "Poids de forme", "Besoin de sommeil",
    "Meilleures performances", "Antécédents de blessure", "Zones fragiles à surveiller",
    "Arrêts récents", "Lieu par défaut", "Créneau habituel", "Terrain accessible",
    "Équipement", "Sports croisés pratiqués", "Ce qui me motive",
    "Ce qui ne marche pas avec moi", "Sujets à ne pas commenter spontanément",
    "Tolérance au risque", "Quand me poser une question plutôt que supposer",
]


def extract_labels(text: str) -> list:
    """Libellés de premier niveau du modèle, normalisés, dans l'ordre du fichier."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    out = []
    for line in text.splitlines():
        m = _TOP_LABEL_RE.match(line)
        if m:
            out.append(L.normalize_label(m.group(1)))
    return out


# Un appel `_pick(b, "...", "...")` (arguments littéraux uniquement — le seul
# style utilisé par `parse_profile`, jamais une variable).
_PICK_CALL_RE = re.compile(r"_pick\(\s*b\s*,\s*((?:\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')"
                            r"(?:\s*,\s*(?:\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'))*)\)")
_STRING_LITERAL_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'')


def _parse_profile_source() -> str:
    """Corps de `def parse_profile(...)` dans `arc_legacy.py`, jusqu'à la
    prochaine définition de fonction de premier niveau (ou la fin du fichier)."""
    text = ARC_LEGACY.read_text(encoding="utf-8")
    start = text.index("\ndef parse_profile(")
    rest = text[start + 1:]
    next_def = re.search(r"\ndef ", rest[1:])
    return rest[: next_def.start() + 1] if next_def else rest


def pick_literals_in_parse_profile() -> list:
    """Le PREMIER libellé littéral de chaque appel `_pick(b, ...)` dans
    `parse_profile` — lu directement dans le CODE SOURCE, jamais recopié à la
    main ici. Seul le premier argument est le libellé CANONIQUE, celui que le
    modèle actuel doit porter (`_pick` le préfère avant tout repli) : les
    arguments suivants sont des alias de secours pour un LIBELLÉ PLUS ANCIEN
    (ex. « fc seuil » pour d'anciens profils écrits avant que le modèle ne dise
    « FC au seuil ») — par construction absents du modèle actuel, ils feraient
    échouer le test à tort s'ils étaient exigés eux aussi."""
    literals = []
    for call in _PICK_CALL_RE.finditer(_parse_profile_source()):
        first = next(_STRING_LITERAL_RE.finditer(call.group(1)), None)
        if first:
            literals.append(first.group(1) if first.group(1) is not None else first.group(2))
    return literals


class TestParseProfileLabelsExistInTemplate(unittest.TestCase):
    """Le garde-fou réel (voir docstring du module) : aucun instantané, une
    lecture directe de `arc_legacy.parse_profile` comparée au modèle actuel via
    `arc_legacy._pick` lui-même."""

    def test_every_pick_literal_resolves_against_the_template(self):
        template_labels = extract_labels(TEMPLATE.read_text(encoding="utf-8"))
        # Valeur non vide arbitraire : `_pick` ne regarde que les CLÉS du dict,
        # jamais leur valeur — voir `arc_legacy._pick`.
        bullets = {label: "x" for label in template_labels}
        literals = pick_literals_in_parse_profile()
        self.assertTrue(literals, "aucun appel _pick trouvé dans parse_profile — "
                                   "ce test ne vérifierait alors plus rien")
        missing = [lit for lit in literals if L._pick(bullets, lit) is None]
        self.assertEqual(missing, [],
                          f"libellé(s) attendu(s) par parse_profile absent(s) du modèle actuel : {missing}")


class TestRunnerProfileTemplateLabelsUnchanged(unittest.TestCase):
    """Répertoire de non-régression complémentaire — voir docstring du module :
    utile en revue de code, mais PAS le garde-fou principal."""

    def setUp(self):
        self.current = extract_labels(TEMPLATE.read_text(encoding="utf-8"))

    def test_every_pre_existing_label_still_present(self):
        missing = [label for label in PRE_EXISTING_LABELS if L.normalize_label(label) not in self.current]
        self.assertEqual(missing, [], f"libellé(s) renommé(s) ou supprimé(s) du modèle : {missing}")

    def test_pre_existing_labels_keep_their_relative_order(self):
        """Renommer un libellé EN PLACE ne serait pas attrapé par le test de
        présence seul si, par malchance, le nouveau nom coïncidait avec un
        libellé déjà attendu ailleurs (aucun cas réel aujourd'hui, mais un
        gel d'ordre relatif est une garantie supplémentaire à coût nul)."""
        expected_order = [L.normalize_label(label) for label in PRE_EXISTING_LABELS]
        current_filtered = [label for label in self.current if label in expected_order]
        self.assertEqual(current_filtered, expected_order)

    def test_new_section_does_not_rename_existing_labels(self):
        """Preuve directe pour #62 : le libellé exact de chaque champ physio/
        historique/matériel préexistant reste un texte strictement identique
        (pas seulement « normalisable pareil »)."""
        text = TEMPLATE.read_text(encoding="utf-8")
        for label in ("FC max", "FC de repos de référence", "FC au seuil", "Poids de forme",
                      "Meilleures performances", "Lieu par défaut", "Créneau habituel"):
            self.assertIn(f"**{label}**", text, f"libellé exact absent : « {label} »")


class TestExtractLabelsHelper(unittest.TestCase):
    """Les helpers eux-mêmes doivent détecter une régression injectée — sans
    quoi ils passeraient toujours, quel que soit le contenu du modèle/du code."""

    def test_detects_a_renamed_label(self):
        text = "# Profil\n\n## Physiologie\n\n- **FC maximale** :\n"
        self.assertNotIn(L.normalize_label("FC max"), extract_labels(text))

    def test_detects_a_removed_label(self):
        text = "# Profil\n\n## Physiologie\n\n- **Sexe** :\n"
        self.assertNotIn(L.normalize_label("FC max"), extract_labels(text))

    def test_pick_literals_are_found(self):
        literals = pick_literals_in_parse_profile()
        self.assertIn("fc max", literals)
        self.assertIn("lieu par defaut", literals)

    def test_pick_literal_check_detects_a_missing_template_label(self):
        """Le garde-fou détecte bien un désaccord parseur/modèle : un libellé que
        `_pick` chercherait mais qu'aucun modèle ne fournit."""
        bullets = {"fc max": "x"}  # « fc de repos de reference » absent
        self.assertIsNone(L._pick(bullets, "fc de repos de reference"))


if __name__ == "__main__":
    unittest.main()
