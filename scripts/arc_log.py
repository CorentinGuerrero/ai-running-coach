#!/usr/bin/env python3
"""arc_log.py — Arithmétique et correspondance catalogue pour `/log` (#67).

Le skill `log` fait analyser une saisie libre par le modèle ("2 gels + 500 ml
au km 15, genou gauche 3/10, RPE 7") : le modèle en extrait des ENTITÉS
(quel produit, quelle quantité, quelle zone douloureuse, quel score...), mais
ne fait JAMAIS lui-même la conversion catalogue ni les sommes — un LLM invente
parfois un chiffre qui a l'air plausible. Ce module fait ce calcul, en pur
stdlib, déterministe et testable indépendamment du modèle : JSON en entrée
(entités extraites), JSON en sortie (macros calculées, correspondances
catalogue, produits inconnus/ambigus, douleur normalisée, drapeau de
consultation).

Le catalogue produit (`resources/nutrition/catalogue-produits-*.md`, voir
`agents/nutritionist.md`) est un tableau Markdown à trois colonnes au moins :

    | Produit | Portion | Glucides |
    |---|---|---|
    | Gel Fixture Test | 1 sachet (40 g) | 32 g |

Correspondance produit : accents et casse ignorés, pluriel français simple
toléré ("gels" → "gel"), et une correspondance PARTIELLE par mot entier est
acceptée ("gel" retrouve "Gel Fixture Test") — mais si plusieurs produits
distincts correspondent, c'est une AMBIGUÏTÉ (jamais une devinette), et si
aucun catalogue n'est fourni ou qu'aucun produit ne correspond, c'est un
produit INCONNU : dans les deux cas, `carbs_g` est OMIS pour cette entrée
plutôt qu'inventé — à l'agent appelant de demander la valeur à l'athlète (voir
`skills/log/SKILL.md`).

Usage
-----
    python3 scripts/arc_log.py --input entree.json
    echo '{"nutrition_items": [...]}' | python3 scripts/arc_log.py

Entrée JSON (toutes les clés sont optionnelles)
------------------------------------------------
    {
      "catalogue_paths": ["resources/nutrition/catalogue-produits-famille.md"],
      "nutrition_items": [{"product": "gels", "qty": "2"}],
      "fluid_entries": ["500 ml", "0,5 l"],
      "pain": [{"location": "genou gauche", "score": "3"}],
      "rpe": "7",
      "pain_consult_threshold": 7.0
    }

`catalogue_paths` omis → résolu par le motif
`resources/nutrition/catalogue-produits-*.md` depuis la racine du dépôt (celle
de ce script, `parents[1]`) ; liste vide explicite → aucun catalogue (tous les
`nutrition_items` ressortent `unknown`, raison `no_catalogue`).

Sortie JSON
-----------
    {
      "nutrition": {
        "matched": [{"input": "gels", "matched_product": "Gel Fixture Test",
                      "qty": 2.0, "carbs_g": 64.0}],
        "unknown": [], "ambiguous": [], "carbs_g": 64.0
      },
      "fluid_intake_ml": 500.0,
      "pain": [{"location": "genou gauche", "score": 3.0, "consult": false}],
      "rpe": 7.0,
      "warnings": []
    }

Bibliothèque standard uniquement (CONTRIBUTING.md).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOGUE_GLOB = "resources/nutrition/catalogue-produits-*.md"

# Même valeur que `arc_guardrails.PAIN_CONSULT_THRESHOLD` (#57) : une douleur
# déclarée à ce score ou au-delà déclenche une recommandation de consultation
# immédiate, avant même le prochain bilan matinal. `tests/data/test_arc_log.py`
# verrouille l'égalité des deux constantes pour qu'elles ne divergent jamais
# silencieusement (le même motif que `arc_contract.RULE_ID_RE` vs
# `arc_guardrails.RULE_IDS`).
PAIN_CONSULT_THRESHOLD = 7.0

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_SPACE_RE = re.compile(r"[^a-z0-9 ]+")
_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
_VOLUME_RE = re.compile(r"(?P<value>-?\d+(?:[.,]\d+)?)\s*(?P<unit>ml|millilitres?|l|litres?)\b", re.IGNORECASE)


class ArcLogError(ValueError):
    """Entrée malformée (JSON invalide, quantité illisible...)."""


# ---------------------------------------------------------------------------
# Normalisation de texte
# ---------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_name(text: str) -> str:
    """Minuscules, sans accents, ponctuation réduite à des espaces, espaces compactés."""
    lowered = _strip_accents(text).lower()
    cleaned = _NON_ALNUM_SPACE_RE.sub(" ", lowered)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def _singularize_word(word: str) -> str:
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]
    return word


def _singular_forms(phrase: str) -> list:
    """Pluriel français simple, MOT PAR MOT : "gels fixture test" → aussi
    "gel fixture test" (et pas seulement la dernière lettre de la phrase
    entière, qui manquerait "gels" en tête de phrase).

    Heuristique volontairement minimale (pas de dictionnaire) : un mot qui se
    termine par "s" et compte plus de trois lettres essaie aussi sa forme sans
    "s" — les invariants ("bras", "gaz"...) ne sont pas des produits de
    ravitaillement plausibles dans ce contexte, le risque de faux positif est
    accepté."""
    words = phrase.split(" ")
    singular_words = [_singularize_word(w) for w in words]
    forms = {phrase, " ".join(singular_words)}
    return list(forms)


def parse_quantity(raw) -> float:
    """"2" → 2.0, "0,5" → 0.5, 3 → 3.0. Lève `ArcLogError` si illisible."""
    if isinstance(raw, (int, float)):
        return float(raw)
    if raw is None:
        raise ArcLogError("quantité absente")
    text = str(raw).strip().replace(",", ".")
    match = _NUMBER_RE.match(text.replace(",", "."))
    if not match:
        raise ArcLogError(f"quantité illisible : {raw!r}")
    return float(match.group(0))


def parse_volume_ml(raw) -> float:
    """"500 ml" → 500.0, "0,5 l" → 500.0, "1l" → 1000.0, nombre nu → millilitres.

    Lève `ArcLogError` si aucune unité reconnue n'est trouvée dans une chaîne."""
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    match = _VOLUME_RE.search(text)
    if not match:
        # Nombre nu sans unité : traité comme des millilitres (convention du
        # skill `log` — voir `skills/log/SKILL.md`, "l'entité extraite porte
        # déjà l'unité résolue par le modèle si le texte source était ambigu").
        try:
            return parse_quantity(text)
        except ArcLogError:
            raise ArcLogError(f"volume illisible : {raw!r}") from None
    value = float(match.group("value").replace(",", "."))
    unit = match.group("unit").lower()
    if unit.startswith("l"):
        return value * 1000.0
    return value


# ---------------------------------------------------------------------------
# Catalogue produit
# ---------------------------------------------------------------------------

_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|\s*$")


def _split_row(line: str) -> list:
    match = _TABLE_ROW_RE.match(line.strip())
    if not match:
        return []
    return [cell.strip() for cell in match.group(1).split("|")]


def _first_number(text: str) -> Optional[float]:
    match = _NUMBER_RE.search(text.replace(",", "."))
    return float(match.group(0)) if match else None


def parse_catalogue(text: str) -> list:
    """Extrait les lignes `{name, carbs_g}` d'un tableau Markdown "Produit | ... | Glucides".

    Insensible à la position/casse des colonnes : seules "Produit" (nom) et une
    colonne dont l'en-tête contient "glucide"/"carb" sont requises. Une ligne
    de tableau qui ne peut pas être rattachée à un nombre de glucides est
    ignorée silencieusement (catalogue partiel — ex. ligne de séparation, ou
    produit dont seule la portion est renseignée)."""
    products: list = []
    header: Optional[list] = None
    name_idx = carbs_idx = None
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        if _TABLE_SEPARATOR_RE.match(line.strip()):
            continue
        cells = _split_row(line)
        if not cells:
            continue
        if header is None:
            header = [normalize_name(c) for c in cells]
            for idx, cell in enumerate(header):
                if name_idx is None and "produit" in cell:
                    name_idx = idx
                if carbs_idx is None and ("glucide" in cell or "carb" in cell):
                    carbs_idx = idx
            continue
        if name_idx is None or carbs_idx is None or len(cells) <= max(name_idx, carbs_idx):
            continue
        name = cells[name_idx].strip()
        carbs_cell = cells[carbs_idx].strip()
        if not name or not carbs_cell:
            continue
        carbs = _first_number(carbs_cell)
        if carbs is None:
            continue
        products.append({"name": name, "carbs_g": carbs})
    return products


def load_catalogue(paths) -> list:
    products: list = []
    for path in paths:
        p = Path(path)
        if not p.is_absolute():
            p = REPO_ROOT / p
        if not p.exists():
            continue
        products.extend(parse_catalogue(p.read_text(encoding="utf-8")))
    return products


def resolve_catalogue_paths(explicit) -> list:
    if explicit is not None:
        return list(explicit)
    return sorted(str(p.relative_to(REPO_ROOT)) for p in REPO_ROOT.glob(DEFAULT_CATALOGUE_GLOB))


def match_product(query: str, catalogue: list):
    """Rend `("matched", produit)`, `("ambiguous", [noms])` ou `("unknown", None)`."""
    if not catalogue:
        return "unknown", None
    nq_forms = set(_singular_forms(normalize_name(query)))
    exact = [p for p in catalogue if normalize_name(p["name"]) in nq_forms]
    if len(exact) == 1:
        return "matched", exact[0]
    if len(exact) > 1:
        names = sorted({p["name"] for p in exact})
        if len(names) == 1:
            return "matched", exact[0]
        return "ambiguous", names

    partial = []
    for product in catalogue:
        words = set(normalize_name(product["name"]).split())
        if nq_forms & words:
            partial.append(product)
    names = sorted({p["name"] for p in partial})
    if len(names) == 1:
        return "matched", partial[0]
    if len(names) > 1:
        return "ambiguous", names
    return "unknown", None


# ---------------------------------------------------------------------------
# Calcul principal
# ---------------------------------------------------------------------------

def compute_nutrition(items: list, catalogue: list) -> dict:
    matched, unknown, ambiguous = [], [], []
    total_carbs = 0.0
    for item in items:
        product_name = str(item.get("product", "")).strip()
        try:
            qty = parse_quantity(item.get("qty", 1))
        except ArcLogError as exc:
            unknown.append({"input": product_name, "reason": str(exc)})
            continue
        if not product_name:
            unknown.append({"input": product_name, "reason": "nom de produit vide"})
            continue
        if not catalogue:
            unknown.append({"input": product_name, "qty": qty, "reason": "no_catalogue"})
            continue
        status, result = match_product(product_name, catalogue)
        if status == "matched":
            carbs = result["carbs_g"] * qty
            total_carbs += carbs
            matched.append({
                "input": product_name,
                "matched_product": result["name"],
                "qty": qty,
                "carbs_g": round(carbs, 2),
            })
        elif status == "ambiguous":
            ambiguous.append({"input": product_name, "qty": qty, "candidates": result})
        else:
            unknown.append({"input": product_name, "qty": qty, "reason": "unknown_product"})
    return {
        "matched": matched,
        "unknown": unknown,
        "ambiguous": ambiguous,
        "carbs_g": round(total_carbs, 2) if matched else None,
    }


def compute_fluids(entries: list) -> Optional[float]:
    if not entries:
        return None
    total = 0.0
    for entry in entries:
        total += parse_volume_ml(entry)
    return round(total, 2)


def compute_pain(entries: list, threshold: float) -> list:
    result = []
    for entry in entries:
        location = str(entry.get("location", "")).strip()
        score = parse_quantity(entry.get("score"))
        result.append({
            "location": location,
            "score": score,
            "consult": score >= threshold,
        })
    return result


def process(payload: dict) -> dict:
    catalogue_paths = resolve_catalogue_paths(payload.get("catalogue_paths"))
    catalogue = load_catalogue(catalogue_paths)

    warnings = []
    out: dict = {"warnings": warnings}

    nutrition_items = payload.get("nutrition_items") or []
    if nutrition_items:
        out["nutrition"] = compute_nutrition(nutrition_items, catalogue)

    fluid_entries = payload.get("fluid_entries") or []
    if fluid_entries:
        fluid_ml = compute_fluids(fluid_entries)
        if fluid_ml is not None:
            out["fluid_intake_ml"] = fluid_ml

    pain_entries = payload.get("pain") or []
    if pain_entries:
        threshold = float(payload.get("pain_consult_threshold", PAIN_CONSULT_THRESHOLD))
        if len(pain_entries) > 10:
            warnings.append("pain : plus de 10 entrées, doublon probable (voir workspace-data-contract)")
        out["pain"] = compute_pain(pain_entries, threshold)

    if "rpe" in payload and payload["rpe"] is not None:
        rpe = parse_quantity(payload["rpe"])
        if not (0 <= rpe <= 10):
            warnings.append(f"rpe : {rpe} hors plage 0-10")
        out["rpe"] = rpe

    if "position" in payload and payload["position"]:
        out["position"] = str(payload["position"]).strip()

    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=None, help="Fichier JSON d'entrée (défaut : stdin)")
    parser.add_argument("--output", type=Path, default=None, help="Fichier JSON de sortie (défaut : stdout)")
    args = parser.parse_args(argv)

    raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERREUR : JSON d'entrée invalide — {exc}", file=sys.stderr)
        return 1

    try:
        result = process(payload)
    except ArcLogError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
