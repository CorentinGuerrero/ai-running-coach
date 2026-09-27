"""Palier B — libellés du modèle Runner_Profile inchangés (#62).

`templates/Runner_Profile.template.md` est lu par `arc_legacy.parse_profile` :
un libellé (`- **Libellé** :`) qui change de forme casse silencieusement la
lecture de tout profil déjà rempli par un athlète — c'est exactement la classe
de bug que le palier B existe pour attraper (voir l'en-tête de
`test_prompt_lint.py`).

`PRE_EXISTING_LABELS` est un instantané, normalisé comme `arc_legacy.
normalize_label` le ferait, des libellés de premier niveau présents dans le
modèle AVANT #62 (indices de performance ITRA/UTMB). Ce test n'interdit pas
d'AJOUTER un libellé — seulement d'en renommer, réordonner au point de le
faire disparaître, ou en supprimer un : #62 n'a ajouté QUE de nouvelles puces
sous une nouvelle section « Indices de performance ».
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


class TestRunnerProfileTemplateLabelsUnchanged(unittest.TestCase):
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
    """Le test lui-même doit détecter une régression injectée — sans quoi il
    passerait toujours, quel que soit le contenu du modèle."""

    def test_detects_a_renamed_label(self):
        text = "# Profil\n\n## Physiologie\n\n- **FC maximale** :\n"
        self.assertNotIn(L.normalize_label("FC max"), extract_labels(text))

    def test_detects_a_removed_label(self):
        text = "# Profil\n\n## Physiologie\n\n- **Sexe** :\n"
        self.assertNotIn(L.normalize_label("FC max"), extract_labels(text))


if __name__ == "__main__":
    unittest.main()
