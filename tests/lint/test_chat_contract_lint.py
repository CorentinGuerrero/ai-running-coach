"""La page Coach lit les champs du contrat d'évènements, pas des noms approximatifs.

Revue : `renderCost` lisait `u.input` / `u.output` / `u.cache_read` alors que les backends
émettent `input_tokens` / `output_tokens` / `cache_read_tokens` — le compteur de jetons ne
s'affichait jamais, sans qu'aucun test ne le voie.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONTRACT = REPO / "scripts/arc_chat_backend.py"
CHAT_JS = REPO / "web/js/chat.js"


def usage_fields() -> list:
    """Champs de l'évènement `usage` tels que décrits dans le contrat (commentaire d'en-tête)."""
    text = CONTRACT.read_text(encoding="utf-8")
    block = re.search(r"#\s+usage\s+\{(.*?)\}", text, re.S)
    assert block, "description de l'évènement usage introuvable dans arc_chat_backend.py"
    return re.findall(r'"([a-z_]+)"', block.group(1))


class ChatContractLint(unittest.TestCase):
    def test_usage_fields_are_the_contract_ones(self):
        fields = usage_fields()
        self.assertIn("input_tokens", fields)
        source = CHAT_JS.read_text(encoding="utf-8")
        for field in fields:
            self.assertIn(field, source, f"chat.js ne lit pas « {field} » de l'évènement usage")

    def test_no_legacy_usage_field_names(self):
        source = CHAT_JS.read_text(encoding="utf-8")
        for legacy in ("u.input ", "u.input)", "u.output ", "u.output)", "u.cache_read ", "u.cache_read)"):
            self.assertNotIn(legacy, source, legacy)


if __name__ == "__main__":
    unittest.main()
