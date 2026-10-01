"""Palier B — la CSP du tableau de bord (`default-src 'self'`) interdit script et style en ligne.

Lecture statique de `web/*.html` : aucune balise `<script>` sans `src`, aucun attribut
`style=` ni gestionnaire `on…=`, aucune balise `<style>`. Attrape avant la revue une
page (`chat.html`, `index.html`, …) qui serait silencieusement cassée par la CSP.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
PAGES = sorted((REPO / "web").glob("*.html"))


class TestWebPagesRespectCsp(unittest.TestCase):
    def test_there_are_pages_to_check(self):
        names = {p.name for p in PAGES}
        self.assertIn("index.html", names)
        self.assertIn("chat.html", names)

    def test_no_inline_script_style_or_handler(self):
        for page in PAGES:
            html = page.read_text(encoding="utf-8")
            with self.subTest(page=page.name):
                for m in re.finditer(r"<script\b([^>]*)>", html, re.IGNORECASE):
                    self.assertRegex(m.group(1), r"\bsrc\s*=", f"{page.name} : <script> en ligne")
                self.assertNotRegex(html, r"(?i)<style\b", f"{page.name} : balise <style> en ligne")
                self.assertNotRegex(html, r"(?i)\sstyle\s*=", f"{page.name} : attribut style= en ligne")
                self.assertNotRegex(html, r"(?i)\son[a-z]+\s*=", f"{page.name} : gestionnaire on…= en ligne")


if __name__ == "__main__":
    unittest.main()
