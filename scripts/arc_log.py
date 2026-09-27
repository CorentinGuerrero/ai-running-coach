#!/usr/bin/env python3
"""arc_log.py — Arithmétique, correspondance catalogue et fusion pour `/log` (#67).

Le skill `log` fait analyser une saisie libre par le modèle ("2 gels + 500 ml
au km 15, genou gauche 3/10, RPE 7") : le modèle en extrait des ENTITÉS (quel
produit, quelle quantité, quelle zone douloureuse, quel score...), mais ne
fait JAMAIS lui-même la conversion catalogue, les sommes, ni la fusion avec un
fichier existant — un LLM invente parfois un chiffre qui a l'air plausible, et
rien ne le rend idempotent. Ce module fait tout ce calcul, en pur stdlib,
déterministe et testable indépendamment du modèle : JSON en entrée (entités
extraites), JSON en sortie (macros calculées, correspondances catalogue,
produits inconnus/ambigus, douleur normalisée, fusion avec le fichier
existant, détection de doublon).

Le catalogue produit (`resources/nutrition/catalogue-produits-*.md`, voir
`agents/nutritionist.md`) est un tableau Markdown à trois colonnes au moins :

    | Produit | Portion | Glucides |
    |---|---|---|
    | Gel Fixture Test | 1 sachet (40 g) | 32 g |

Correspondance produit : accents et casse ignorés, pluriel français simple
toléré des DEUX côtés — la requête ("gels") ET le nom du catalogue lui-même
("Barres" au pluriel dans un catalogue mal saisi) — et une correspondance
PARTIELLE par mot entier est acceptée ("gel" retrouve "Gel Fixture Test").
Mais si plusieurs produits distincts correspondent, c'est une AMBIGUÏTÉ
(jamais une devinette), et si aucun catalogue n'est fourni ou qu'aucun
produit ne correspond, c'est un produit INCONNU : dans les deux cas,
`carbs_g` est OMIS pour cette entrée plutôt qu'inventé — à l'agent appelant
de demander la valeur à l'athlète (voir `skills/log/SKILL.md`).

Ce module ne récupère PAS lui-même la valeur `[injury_risk].pain_consult_threshold`
en dur : il la résout depuis la configuration vivante du workspace
(`arc_index.load_config` + `arc_guardrails.injury_risk_settings`), pour ne
jamais diverger d'une valeur personnalisée par l'athlète.

Usage
-----
    python3 scripts/arc_log.py --input entree.json
    echo '{"nutrition_items": [...]}' | python3 scripts/arc_log.py
    python3 scripts/arc_log.py --workspace /chemin/vers/workspace --input entree.json

Entrée JSON (toutes les clés sont optionnelles)
------------------------------------------------
    {
      "catalogue_paths": ["resources/nutrition/catalogue-produits-famille.md"],
      "nutrition_items": [{"product": "gels", "qty": "2"}],
      "fluid_entries": ["500 ml", "50cl", "2 x 500 ml"],
      "pain": [{"location": "genou gauche", "score": "3"}],
      "rpe": "7",
      "pain_consult_threshold": 7.0,
      "raw_text": "2 gels + 500 ml au km 15, genou gauche 3/10, RPE 7",
      "timestamp": "2026-09-24T18:32:00+02:00",
      "existing_activity_arc": {"garmin_activity_id": 90000000001, "carbs_g": 32},
      "existing_pain": [{"location": "cheville", "score": 2}],
      "existing_log_entries": ["2 gels + 500 ml au km 15, genou gauche 3/10, RPE 7"]
    }

`catalogue_paths` omis → résolu par le motif
`resources/nutrition/catalogue-produits-*.md` depuis la racine du dépôt (celle
de ce script, `parents[1]`) ; liste vide explicite → aucun catalogue (tous les
`nutrition_items` ressortent `unknown`, raison `no_catalogue`).

`pain_consult_threshold` explicite prime sur la configuration ; sans lui, ce
script lit `config/workspace(.user).toml` du `--workspace` donné (ou du
répertoire courant) via `arc_guardrails.injury_risk_settings`, avec repli sur
`arc_guardrails.PAIN_CONSULT_THRESHOLD` si la configuration est illisible.

`raw_text` + `existing_log_entries` (les lignes de provenance déjà trouvées
sous le bloc ```arc du fichier visé, voir « Idempotence » plus bas) permettent
de détecter un doublon : un `raw_text` déjà présent, normalisé (espaces,
casse), met `"duplicate": true` dans la sortie et **n'ajoute aucune fusion**
(`activity_merge`/`pain_merge` absents) — à l'agent de demander avant de
compter deux fois la même déclaration.

`existing_activity_arc`/`existing_pain` déclenchent le calcul de fusion
(`activity_merge`, `pain_merge`) : addition des glucides/liquide, remplacement
du dernier RPE déclaré, jamais d'écrasement d'une clé non concernée par `/log`
(ce module ne touche jamais `garmin_activity_id`, `distance_m`, etc. — il rend
seulement les clés à fusionner, l'écriture du fichier complet reste faite par
l'agent, qui a la vue d'ensemble du Markdown existant, narratif compris).

Sortie JSON (clés présentes seulement si les entrées correspondantes le sont)
------------------------------------------------------------------------------
    {
      "nutrition": {
        "matched": [{"input": "gels", "matched_product": "Gel Fixture Test",
                      "qty": 2.0, "carbs_g": 64.0}],
        "unknown": [], "ambiguous": [], "carbs_g": 64.0
      },
      "fluids": {"matched": [...], "unknown": [...], "fluid_intake_ml": 500.0},
      "pain": {"entries": [{"location": "genou gauche", "score": 3.0, "consult": false}],
               "unknown": [], "consult_threshold": 7.0},
      "rpe": 7.0,
      "duplicate": false,
      "provenance_line": "[/log 2026-09-24T18:32:00+02:00] 2 gels + 500 ml au km 15, genou gauche 3/10, RPE 7",
      "activity_merge": {"carbs_g": 64.0, "fluid_intake_ml": 500.0, "rpe": 7.0},
      "pain_merge": [{"location": "cheville", "score": 2}, {"location": "genou gauche", "score": 3.0, "consult": false}],
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOGUE_GLOB = "resources/nutrition/catalogue-produits-*.md"

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from coach_setup import workspace_root  # noqa: E402
    import arc_index as _arc_index  # noqa: E402
    import arc_guardrails as _arc_guardrails  # noqa: E402
except Exception:       # pragma: no cover — repli défensif, voir resolve_pain_consult_threshold
    workspace_root = None
    _arc_index = None
    _arc_guardrails = None

# Repli si la configuration du workspace est illisible ou si l'import ci-dessus
# a échoué (environnement minimal, tests unitaires isolés) — même valeur que
# `arc_guardrails.PAIN_CONSULT_THRESHOLD`, jamais une constante dupliquée à la
# main : `tests/data/test_arc_log.py` verrouille que ce module RÉSOUT bien la
# configuration vivante plutôt que de se contenter de ce repli.
FALLBACK_PAIN_CONSULT_THRESHOLD = 7.0

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_SPACE_RE = re.compile(r"[^a-z0-9 ½]+")

# --- Nombres (quantités d'items solides : "2", "0,5", "1 et demi", "deux") ---
_WORD_NUMBERS = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
}
_WORD_NUMBER_ALT = "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True))

# --- Volumes (ml/cl/dl/l, unité OBLIGATOIRE — jamais de repli "nombre nu") ---
_VOLUME_UNITS = {
    "ml": 1.0, "millilitre": 1.0, "millilitres": 1.0,
    "cl": 10.0, "centilitre": 10.0, "centilitres": 10.0,
    "dl": 100.0, "decilitre": 100.0, "decilitres": 100.0,
    "l": 1000.0, "litre": 1000.0, "litres": 1000.0,
}
_VOLUME_UNIT_ALT = "|".join(sorted(_VOLUME_UNITS, key=len, reverse=True))


class ArcLogError(ValueError):
    """Entrée malformée (JSON invalide, quantité/volume illisible, valeur négative...)."""


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
    """Pluriel français simple, MOT PAR MOT, appliqué aux DEUX côtés d'une
    correspondance (la requête de l'athlète ET le nom du catalogue) : "gels
    fixture test" → aussi "gel fixture test", et un catalogue mal saisi au
    pluriel ("Barres Choco") se retrouve tout autant.

    Heuristique volontairement minimale (pas de dictionnaire) : un mot qui se
    termine par "s" et compte plus de trois lettres essaie aussi sa forme sans
    "s" — les invariants ("bras", "gaz"...) ne sont pas des produits de
    ravitaillement plausibles dans ce contexte, le risque de faux positif est
    accepté."""
    words = phrase.split(" ")
    singular_words = [_singularize_word(w) for w in words]
    forms = {phrase, " ".join(singular_words)}
    return list(forms)


def _reject_negative(text: str, what: str) -> None:
    if text.strip().startswith("-"):
        raise ArcLogError(f"{what} négatif refusé : {text!r}")


def parse_quantity(raw) -> float:
    """Quantité d'un item solide ("2 gels" → qty). Ancré (`fullmatch`) : un
    texte qui ne correspond pas EXACTEMENT à une forme reconnue est refusé —
    jamais une extraction partielle qui ignorerait le reste ("3 x 40 g" ne
    doit jamais silencieusement devenir 3, la portion "40 g" contredirait
    peut-être le catalogue).

    Formes reconnues : nombre (point ou virgule décimale), nombre + "½" ou
    "et demi(e)" (fraction), mot ("un".."dix"), mot + fraction. Négatif
    toujours refusé. Lève `ArcLogError` sinon."""
    if isinstance(raw, (int, float)):
        if raw < 0:
            raise ArcLogError(f"quantité négative refusée : {raw!r}")
        return float(raw)
    if raw is None:
        raise ArcLogError("quantité absente")
    text = str(raw).strip().lower()
    _reject_negative(text, "quantité")

    # Nombre nu, éventuellement suivi d'une fraction ("2", "0,5", "1 et demi", "1½").
    m = re.fullmatch(r"(?P<num>\d+(?:[.,]\d+)?)\s*(?:(?P<half>½)|et\s+demie?)?", text)
    if m:
        value = float(m.group("num").replace(",", "."))
        if m.group("half") or "et" in text:
            value += 0.5
        return value

    # "½" seul.
    if text == "½":
        return 0.5

    # Mot ("un".."dix"), éventuellement + fraction.
    m = re.fullmatch(rf"(?P<word>{_WORD_NUMBER_ALT})(?:\s*(?P<half>½)|\s+et\s+demie?)?", text)
    if m:
        value = float(_WORD_NUMBERS[m.group("word")])
        if m.group("half") or "et" in text:
            value += 0.5
        return value

    raise ArcLogError(f"quantité illisible : {raw!r}")


def parse_volume_ml(raw) -> float:
    """Volume déclaré, TOUJOURS avec une unité explicite reconnue (ml/cl/dl/l) —
    jamais de repli "nombre nu = millilitres" : un nombre sans unité, ou une
    unité non reconnue ("bidon"), doit être refusé pour que l'appelant le
    range dans `fluids.unknown` plutôt que d'inventer un volume. Ancré
    (`fullmatch`) pour la même raison qu'au-dessus.

    Formes reconnues : "N unité", "N x M unité" (N sachets/bidons de M chacun),
    "N et demi unité"/"N½ unité"/"½ unité", "un|deux unité". Unités : ml, cl,
    dl, l (et leurs formes longues). Négatif toujours refusé."""
    if isinstance(raw, (int, float)):
        raise ArcLogError(
            f"volume sans unité refusé (nombre nu {raw!r}) — préciser ml/cl/dl/l"
        )
    text = str(raw).strip().lower()
    _reject_negative(text, "volume")

    unit_alt = _VOLUME_UNIT_ALT

    # "N x M unité" — AVANT le cas simple, sinon "2 x 500 ml" matcherait
    # partiellement et perdrait le facteur "x 500".
    m = re.fullmatch(
        rf"(?P<n>\d+(?:[.,]\d+)?)\s*x\s*(?P<m>\d+(?:[.,]\d+)?)\s*(?P<unit>{unit_alt})", text
    )
    if m:
        n = float(m.group("n").replace(",", "."))
        qty = float(m.group("m").replace(",", "."))
        factor = _VOLUME_UNITS[m.group("unit")]
        return n * qty * factor

    # "N et demi unité" / "N½ unité".
    m = re.fullmatch(
        rf"(?P<num>\d+)\s*(?:(?P<half>½)|et\s+demie?)\s*(?P<unit>{unit_alt})", text
    )
    if m:
        value = float(m.group("num")) + 0.5
        return value * _VOLUME_UNITS[m.group("unit")]

    # "½ unité" seul.
    m = re.fullmatch(rf"½\s*(?P<unit>{unit_alt})", text)
    if m:
        return 0.5 * _VOLUME_UNITS[m.group("unit")]

    # "un|deux unité".
    m = re.fullmatch(rf"(?P<word>un|une|deux)\s*(?P<unit>{unit_alt})", text)
    if m:
        return float(_WORD_NUMBERS[m.group("word")]) * _VOLUME_UNITS[m.group("unit")]

    # "N unité" — cas simple, tenté en dernier (les formes ci-dessus sont
    # toutes des sur-ensembles syntaxiques qui, mal ordonnés, seraient
    # engloutis par celui-ci).
    m = re.fullmatch(rf"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>{unit_alt})", text)
    if m:
        return float(m.group("num").replace(",", ".")) * _VOLUME_UNITS[m.group("unit")]

    raise ArcLogError(f"volume illisible ou unité non reconnue (ml/cl/dl/l attendue) : {raw!r}")


# ---------------------------------------------------------------------------
# Catalogue produit
# ---------------------------------------------------------------------------

_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|\s*$")
_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


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
    """Rend `("matched", produit)`, `("ambiguous", [noms])` ou `("unknown", None)`.

    Pluriel français toléré des DEUX côtés (`_singular_forms`) : la requête de
    l'athlète ET le nom tel qu'écrit dans le catalogue."""
    if not catalogue:
        return "unknown", None
    nq_forms = set(_singular_forms(normalize_name(query)))

    def _matches(product_name: str) -> bool:
        return bool(nq_forms & set(_singular_forms(normalize_name(product_name))))

    exact = [p for p in catalogue if _matches(p["name"])]
    names = sorted({p["name"] for p in exact})
    if len(names) == 1:
        return "matched", exact[0]
    if len(names) > 1:
        return "ambiguous", names

    partial = []
    for product in catalogue:
        words = set(normalize_name(product["name"]).split())
        singular_words = {_singularize_word(w) for w in words}
        if nq_forms & (words | singular_words):
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


def compute_fluids(entries: list) -> dict:
    matched, unknown = [], []
    total = 0.0
    for entry in entries:
        try:
            ml = parse_volume_ml(entry)
        except ArcLogError as exc:
            unknown.append({"input": entry, "reason": str(exc)})
            continue
        matched.append({"input": entry, "fluid_ml": round(ml, 2)})
        total += ml
    return {
        "matched": matched,
        "unknown": unknown,
        "fluid_intake_ml": round(total, 2) if matched else None,
    }


def resolve_pain_consult_threshold(workspace: Optional[Path]) -> float:
    """Résout `[injury_risk].pain_consult_threshold` depuis la configuration
    VIVANTE du workspace (jamais une constante dupliquée à la main, #57) —
    repli sur `arc_guardrails.PAIN_CONSULT_THRESHOLD` si le module n'a pas pu
    être importé ou si la configuration est illisible pour une raison ou une
    autre (workspace minimal, tests)."""
    if _arc_index is None or _arc_guardrails is None:
        return FALLBACK_PAIN_CONSULT_THRESHOLD
    try:
        ws = workspace if workspace is not None else Path.cwd()
        config = _arc_index.load_config(ws)
        return _arc_guardrails.injury_risk_settings(config)["pain_consult_threshold"]
    except Exception:
        return FALLBACK_PAIN_CONSULT_THRESHOLD


def compute_pain(entries: list, threshold: float) -> dict:
    valid, unknown = [], []
    for entry in entries:
        location = str(entry.get("location", "")).strip()
        raw_score = entry.get("score")
        try:
            score = parse_quantity(raw_score)
        except ArcLogError as exc:
            unknown.append({"location": location, "input": raw_score, "reason": str(exc)})
            continue
        if not (0 <= score <= 10):
            unknown.append({
                "location": location, "input": raw_score,
                "reason": f"score hors plage 0-10 : {score!r}",
            })
            continue
        valid.append({
            "location": location,
            "score": score,
            "consult": score >= threshold,
        })
    return {"entries": valid, "unknown": unknown, "consult_threshold": threshold}


def merge_activity(existing: Optional[dict], carbs_g, fluid_intake_ml, rpe) -> dict:
    """Clés à FUSIONNER dans le bloc `activity` existant — jamais le bloc entier :
    l'appelant garde `garmin_activity_id`, `distance_m` et tout le reste
    intacts. `carbs_g`/`fluid_intake_ml` s'ADDITIONNENT à une valeur déjà
    présente (un athlète peut logger deux fois pendant le même effort) ; `rpe`
    REMPLACE (un seul RPE par séance a un sens, le dernier déclaré prime)."""
    existing = existing or {}
    merged: dict = {}
    if carbs_g is not None:
        merged["carbs_g"] = round((existing.get("carbs_g") or 0) + carbs_g, 2)
    if fluid_intake_ml is not None:
        merged["fluid_intake_ml"] = round((existing.get("fluid_intake_ml") or 0) + fluid_intake_ml, 2)
    if rpe is not None:
        merged["rpe"] = rpe
    return merged


def merge_pain(existing_pain: Optional[list], new_entries: list) -> list:
    """Union simple : les entrées de douleur d'un jour s'ACCUMULENT, aucune
    n'est jamais remplacée (#57 — plusieurs zones peuvent être signalées au fil
    de la journée)."""
    return list(existing_pain or []) + list(new_entries)


def _normalize_provenance(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.strip().lower())


def check_duplicate(raw_text: Optional[str], existing_log_entries) -> bool:
    if not raw_text or not existing_log_entries:
        return False
    target = _normalize_provenance(raw_text)
    return any(_normalize_provenance(str(e)) == target for e in existing_log_entries)


def provenance_line(raw_text: str, timestamp: Optional[str] = None) -> str:
    ts = timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"[/log {ts}] {raw_text}"


def process(payload: dict, workspace: Optional[Path] = None) -> dict:
    catalogue_paths = resolve_catalogue_paths(payload.get("catalogue_paths"))
    catalogue = load_catalogue(catalogue_paths)

    warnings: list = []
    out: dict = {"warnings": warnings}

    raw_text = payload.get("raw_text")
    existing_log_entries = payload.get("existing_log_entries") or []
    duplicate = check_duplicate(raw_text, existing_log_entries)
    if raw_text:
        out["duplicate"] = duplicate
        out["provenance_line"] = provenance_line(raw_text, payload.get("timestamp"))

    nutrition_items = payload.get("nutrition_items") or []
    nutrition = None
    if nutrition_items:
        nutrition = compute_nutrition(nutrition_items, catalogue)
        out["nutrition"] = nutrition

    fluid_entries = payload.get("fluid_entries") or []
    fluids = None
    if fluid_entries:
        fluids = compute_fluids(fluid_entries)
        out["fluids"] = fluids

    pain_entries = payload.get("pain") or []
    pain = None
    if pain_entries:
        threshold = payload.get("pain_consult_threshold")
        if threshold is None:
            threshold = resolve_pain_consult_threshold(workspace)
        else:
            threshold = float(threshold)
        if len(pain_entries) > 10:
            warnings.append("pain : plus de 10 entrées, doublon probable (voir workspace-data-contract)")
        pain = compute_pain(pain_entries, threshold)
        out["pain"] = pain

    rpe = None
    if "rpe" in payload and payload["rpe"] is not None:
        try:
            candidate = parse_quantity(payload["rpe"])
        except ArcLogError as exc:
            out["rpe_unknown"] = {"input": payload["rpe"], "reason": str(exc)}
            candidate = None
        else:
            if not (0 <= candidate <= 10):
                # Hors plage : jamais silencieusement accepté (#67, revue de
                # code) — la clé `rpe` n'est PAS posée, `rpe_unknown` force
                # l'agent à confirmer/reformuler plutôt qu'à écrire une valeur
                # hors contrat (0-10, voir workspace-data-contract).
                out["rpe_unknown"] = {"input": payload["rpe"], "reason": f"rpe hors plage 0-10 : {candidate!r}"}
                warnings.append(f"rpe : {candidate} hors plage 0-10, non retenu")
            else:
                rpe = candidate
                out["rpe"] = rpe

    if "position" in payload and payload["position"]:
        out["position"] = str(payload["position"]).strip()

    # Fusion (#67, revue de code — idempotence) : seulement si l'appelant a
    # fourni l'état existant, et jamais pour un doublon détecté (sans quoi une
    # même déclaration relue deux fois compterait double).
    if not duplicate:
        carbs_g = nutrition["carbs_g"] if nutrition else None
        fluid_intake_ml = fluids["fluid_intake_ml"] if fluids else None
        if "existing_activity_arc" in payload and (carbs_g is not None or fluid_intake_ml is not None or rpe is not None):
            out["activity_merge"] = merge_activity(
                payload.get("existing_activity_arc"), carbs_g, fluid_intake_ml, rpe
            )
        if "existing_pain" in payload and pain and pain["entries"]:
            out["pain_merge"] = merge_pain(payload.get("existing_pain"), pain["entries"])

    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=None, help="Fichier JSON d'entrée (défaut : stdin)")
    parser.add_argument("--output", type=Path, default=None, help="Fichier JSON de sortie (défaut : stdout)")
    parser.add_argument("--workspace", default=None, help="Racine du workspace (défaut : résolution standard)")
    args = parser.parse_args(argv)

    raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERREUR : JSON d'entrée invalide — {exc}", file=sys.stderr)
        return 1

    workspace = None
    if args.workspace:
        workspace = Path(args.workspace).expanduser().resolve()
    elif workspace_root is not None:
        try:
            workspace = workspace_root(None)
        except Exception:
            workspace = None

    try:
        result = process(payload, workspace=workspace)
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
