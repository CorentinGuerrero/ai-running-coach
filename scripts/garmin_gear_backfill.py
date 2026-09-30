#!/usr/bin/env python3
"""Rattrapage du matériel Garmin sur l'historique des séances (#145, épopée #131).

#133 attribue la chaussure Garmin aux séances NOUVELLES (`get_activity_gear` à la
synchronisation). Les séances déjà dans le workspace n'ont pas de `gear_id` : la carte
« Matériel » est vide alors que Garmin Connect connaît la paire de chaque séance. Ce
script les rattrape en UN appel Garmin par paire de chaussures (`get_gear_activities`),
jamais un par séance.

    python3 scripts/garmin_gear_backfill.py --workspace <dossier>            # simulation (défaut)
    python3 scripts/garmin_gear_backfill.py --workspace <dossier> --apply    # écrit

Simulation par défaut : rien n'est écrit sans `--apply`. Le rapport donne, par paire, la puce
`### Chaussures` proposée, le nombre de séances rattachées, les km du workspace vs le total
Garmin ; puis les conflits, les séances ambiguës, les séances Garmin absentes du workspace et
les fichiers sans `garmin_activity_id`.

Options : `--since AAAA-MM-JJ` (séances du workspace à partir de cette date seulement),
`--gear UUID` (une seule paire Garmin), `--all-shoes` (propose aussi les paires sans séance
dans la période du workspace, en `(retirée)` quand Garmin les a retirées), `--json` (sortie
machine), `--workspace`, `--tokens-dir`.

CODES DE SORTIE : 0 = succès (simulation ou application complète) ; 1 = succès partiel
(paire injoignable côté Garmin, fichier rejeté par la validation et restauré) ; 2 = usage,
dépendance `garminconnect` absente ou authentification Garmin impossible ; 3 = `--apply`
impossible faute de profil athlète (`planning/Runner_Profile.md`).

EXCEPTION À « stdlib seule » (documentée, comme `skills/fit-download/scripts/download_fit.py`) :
la seule dépendance non standard est `garminconnect`, importée PARESSEUSEMENT dans
`connect_garmin()` — tout le reste du module (planification pure) s'importe et se teste avec la
bibliothèque standard. Comme `download_fit.py`, le script se relance avec l'interpréteur de
`garmin-mcp` (`~/.local/share/uv/tools/garmin-mcp/bin/python3`, ou `GARMIN_PYTHON`) quand
`garminconnect` manque, et lit les mêmes jetons (`~/.garminconnect`, ou `GARMINTOKENS` de
`.mcp.json` — même résolution que `coach_doctor.py`).

RÈGLES (voir docs/garmin-setup.md) :
  - Seul `gearTypeName == "Shoes"`. Jamais `(par défaut)` posé automatiquement.
  - Priorité #133 : une séance qui porte déjà un `gear_id` (athlète ou chat, ou Garmin d'une
    synchronisation antérieure) n'est JAMAIS écrasée ; la divergence est listée. Seul un
    `gear_source: "garmin_unmapped"` (sans `gear_id`) est remplacé.
  - Une séance présente dans deux paires côté Garmin est ambiguë : jamais attribuée, listée.
  - Puce existante avec le même `garmin: <uuid>` : son `gear_id` est réutilisé, la puce n'est
    jamais modifiée. Puce `(ignorée)` : la paire n'est jamais attribuée.
  - `départ N km` d'une puce NOUVELLE = km Garmin de la paire pour les séances Garmin ABSENTES du
    workspace (identifiées par `activityId`, jamais par un total soustrait) : celles du workspace
    sont déjà comptées par leurs fichiers, elles ne peuvent donc pas l'être deux fois. Non calculé
    (avec la raison au rapport) avec `--since`, si la liste Garmin est tronquée ou en erreur, ou si
    des fichiers sans `garmin_activity_id` tombent le même jour qu'une séance Garmin absente.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arc_contract as C  # noqa: E402
import arc_legacy as L  # noqa: E402

GEAR_ACTIVITIES_PAGE = 1000            # plafond `MAX_ACTIVITY_LIMIT` de garminconnect
EXIT_OK, EXIT_PARTIAL, EXIT_USAGE, EXIT_NO_PROFILE = 0, 1, 2, 3
DEFAULT_PROFILE_REL = "planning/Runner_Profile.md"
_DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_KEYWORDS = r"depuis|alerte|d[ée]part|usage\s*:|id\s*:|garmin\s*:"


# ---------------------------------------------------------------------------
# Inventaire Garmin (pur)
# ---------------------------------------------------------------------------

def _clean(value: Any) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text or None


def normalize_shoes(raw_gear: List[dict]) -> List[dict]:
    """`get_gear` → chaussures seulement (`gearTypeName == "Shoes"`), champs normalisés.

    Nom : `displayName`, puis `customMakeModel`, puis « Chaussure Garmin <uuid[:8]> »
    (`displayName` peut être `None` chez Garmin)."""
    shoes = []
    for g in raw_gear or []:
        if not isinstance(g, dict) or str(g.get("gearTypeName") or "").strip().lower() != "shoes":
            continue
        uuid = _clean(g.get("uuid"))
        if not uuid:
            continue
        uuid = uuid.lower()
        begin = _DATE_PREFIX_RE.match(str(g.get("dateBegin") or ""))
        try:
            max_m = float(g.get("maximumMeters") or 0)
        except (TypeError, ValueError):
            max_m = 0.0
        shoes.append({
            "uuid": uuid,
            "name": _clean(g.get("displayName")) or _clean(g.get("customMakeModel")) or f"Chaussure Garmin {uuid[:8]}",
            "retired": str(g.get("gearStatusName") or "").strip().lower() == "retired",
            "date_begin": begin.group(1) if begin else None,
            "max_m": max_m if max_m > 0 else 0.0,
        })
    return shoes


def normalize_gear_activities(raw: Optional[List[dict]]) -> List[dict]:
    """`get_gear_activities` → `[{id, date, distance_m}]` (ids entiers, sans doublon)."""
    out, seen = [], set()
    for a in raw or []:
        try:
            aid = int(a.get("activityId"))
        except (AttributeError, TypeError, ValueError):
            continue
        if aid in seen:
            continue
        seen.add(aid)
        day = _DATE_PREFIX_RE.match(str(a.get("startTimeLocal") or a.get("startTimeGMT") or ""))
        try:
            dist = float(a.get("distance") or 0)
        except (TypeError, ValueError):
            dist = 0.0
        out.append({"id": aid, "date": day.group(1) if day else None, "distance_m": max(dist, 0.0)})
    return out


# ---------------------------------------------------------------------------
# Puces `### Chaussures` (pur)
# ---------------------------------------------------------------------------

def _try_parse(bullet: str) -> Optional[dict]:
    parsed = L.parse_gear("### Chaussures\n\n" + bullet + "\n")
    return parsed[0] if len(parsed) == 1 else None


def safe_bullet_name(name: str, uuid: str) -> str:
    """Nom compatible avec l'analyseur de puces : tirets cadratins, marqueurs `(retirée)`… et
    « : mot-clé » retirés ; repli progressif jusqu'à « Chaussure Garmin <uuid[:8]> »."""
    fallback = f"Chaussure Garmin {uuid[:8]}"
    text = re.sub(r"\s+", " ", str(name or "").replace("**", " ")).strip()
    text = re.sub(r"[—–]", "-", text)
    text = re.sub(r"\(\s*(?:par\s*d[ée]faut|retir[ée]e?|ignor[ée]e?)\s*\)", " ", text, flags=re.I)
    text = re.sub(rf"\s+-\s+(?=(?:{_KEYWORDS}))", " ", text, flags=re.I)
    text = re.sub(rf"\s*:\s*(?=(?:{_KEYWORDS}))", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    for candidate in (text, re.sub(r"\s+", " ", re.sub(r"[^\w /.,+'-]", " ", text)).strip()):
        parsed = _try_parse(f"- {candidate}") if candidate else None
        if parsed and parsed.get("name") == candidate:
            return candidate
    return fallback


def unique_gear_id(name: str, uuid: str, used: set) -> str:
    """Slug `arc_contract.gear_slug(name)` (repli sur l'uuid), suffixé `-2`, `-3`… s'il est déjà pris
    (profil, matériel `### Matériel`, puces proposées dans ce même passage)."""
    base = C.gear_slug(name) or C.gear_slug(f"chaussure garmin {uuid[:8]}") or "chaussure-garmin"
    candidate, n = base, 1
    while candidate in used:
        n += 1
        suffix = f"-{n}"
        candidate = base[: C.GEAR_ID_MAX_LEN - len(suffix)].rstrip("-") + suffix
    used.add(candidate)
    return candidate


def build_bullet(shoe: dict, gear_id: str, depart_km: Optional[int]) -> str:
    """`- <nom> — depuis <date> — alerte N km — départ N km — id: <slug> — garmin: <uuid> (retirée)`.
    Toujours relue par `arc_legacy.parse_gear` : un écart (id, uuid, nom) lève une erreur plutôt
    qu'une puce silencieusement fausse."""
    name = safe_bullet_name(shoe["name"], shoe["uuid"])
    parts = [name]
    if shoe.get("date_begin"):
        parts.append(f"depuis {shoe['date_begin']}")
    if shoe.get("max_m"):
        parts.append(f"alerte {round(shoe['max_m'] / 1000):d} km")
    if depart_km:
        parts.append(f"départ {int(depart_km)} km")
    parts.append(f"id: {gear_id}")
    parts.append(f"garmin: {shoe['uuid']}")
    bullet = "- " + " — ".join(parts) + (" (retirée)" if shoe.get("retired") else "")
    parsed = _try_parse(bullet)
    if not parsed or parsed.get("gear_id") != gear_id or parsed.get("garmin_uuid") != shoe["uuid"] \
            or parsed.get("name") != name:
        raise ValueError(f"puce non relue à l'identique par parse_gear : {bullet!r}")
    return bullet


# ---------------------------------------------------------------------------
# Planification (pure : aucune E/S)
# ---------------------------------------------------------------------------

def _km(meters: float) -> float:
    return round(meters / 1000.0, 1)


def plan(shoes: List[dict], gear_acts: Dict[str, dict], ws_files: List[dict], profile_gear: List[dict],
         *, since: Optional[str] = None, only_gear: Optional[str] = None, all_shoes: bool = False,
         extra_used_ids=(), garmin_defaults=()) -> dict:
    """Plan de rattrapage — entrées :

    - `shoes` : `normalize_shoes` ; `gear_acts` : `{uuid: {"activities": normalize_gear_activities,
      "error": str|None, "truncated": bool}}` ;
    - `ws_files` : une entrée par `activities/*.md` : `{path, date, garmin_activity_id, distance_m,
      gear_id, gear_source, has_block}` ;
    - `profile_gear` : `arc_legacy.parse_gear` (puces existantes, `(ignorée)` comprises).
    """
    only = (only_gear or "").strip().lower() or None
    selected = [s for s in shoes if only is None or s["uuid"] == only]
    by_ws_id = {f["garmin_activity_id"]: f for f in ws_files if f.get("garmin_activity_id") is not None}
    no_id_files = [f for f in ws_files if f.get("garmin_activity_id") is None]
    dated = [f["date"] for f in ws_files if f.get("date")]
    ws_min, ws_max = (min(dated), max(dated)) if dated else (None, None)
    lo = max(ws_min, since) if (ws_min and since) else (since or ws_min)

    profile_by_uuid: Dict[str, List[dict]] = {}
    for g in profile_gear:
        if g.get("garmin_uuid"):
            profile_by_uuid.setdefault(g["garmin_uuid"], []).append(g)
    used_ids = {g["gear_id"] for g in profile_gear} | set(extra_used_ids)
    profile_id_by_uuid = {u: gs[0]["gear_id"] for u, gs in profile_by_uuid.items()}

    # activité Garmin → paires qui la revendiquent (uniquement parmi les paires interrogées)
    claimed: Dict[int, List[str]] = {}
    for s in selected:
        for a in gear_acts.get(s["uuid"], {}).get("activities", []):
            claimed.setdefault(a["id"], []).append(s["uuid"])
    ambiguous_ids = {aid for aid, us in claimed.items() if len(us) > 1}

    result: Dict[str, Any] = {
        "since": since, "gear_filter": only, "all_shoes": all_shoes,
        "workspace_period": [ws_min, ws_max],
        "shoes": [], "assignments": [], "new_bullets": [], "conflicts": [], "ambiguous": [],
        "missing_from_workspace": [], "workspace_without_id": [f["path"] for f in no_id_files],
        "workspace_files": len(ws_files), "workspace_with_id": len(by_ws_id),
        "garmin_defaults": list(garmin_defaults), "skipped_out_of_period": [],
    }
    ordered = sorted(selected, key=lambda s: (s["date_begin"] or "9999", s["name"].lower(), s["uuid"]))
    for shoe in ordered:
        info = gear_acts.get(shoe["uuid"], {})
        acts = info.get("activities", [])
        entry: Dict[str, Any] = {
            "uuid": shoe["uuid"], "name": shoe["name"], "retired": shoe["retired"],
            "garmin_sessions": len(acts), "garmin_km": _km(sum(a["distance_m"] for a in acts)),
            "error": info.get("error"), "truncated": bool(info.get("truncated")),
            "matched": 0, "workspace_km": 0.0, "to_write": 0, "already": 0, "conflicts": 0,
            "ambiguous": 0, "before_since": 0, "missing_from_workspace": 0,
            "status": None, "gear_id": None, "bullet": None, "depart_km": None, "depart_note": None,
        }
        result["shoes"].append(entry)
        if info.get("error"):
            entry["status"] = "error"
            continue
        in_period = [a for a in acts if a["date"] and lo and ws_max and lo <= a["date"] <= ws_max]
        if not in_period:
            entry["status"] = "out_of_period"
            result["skipped_out_of_period"].append(shoe["uuid"])
            if not all_shoes:
                continue
        existing = profile_by_uuid.get(shoe["uuid"], [])
        if len(existing) > 1:
            entry["status"] = "duplicate_in_profile"
            entry["depart_note"] = "uuid présent sur plusieurs puces du profil : rien n'est attribué"
            continue
        if existing and existing[0].get("ignored"):
            entry["status"] = "ignored"
            entry["gear_id"] = existing[0]["gear_id"]
            continue
        if existing:
            entry["status"] = "existing"
            entry["gear_id"] = existing[0]["gear_id"]
        else:
            if entry["status"] != "out_of_period":
                entry["status"] = "new"
            entry["gear_id"] = unique_gear_id(shoe["name"], shoe["uuid"], used_ids)
        gear_id = entry["gear_id"]

        # --- séances du workspace ---
        missing = []
        for a in acts:
            f = by_ws_id.get(a["id"])
            if f is None:
                if a["id"] in ambiguous_ids:
                    continue   # signalée plus bas, jamais comptée dans `départ` (deux paires la revendiquent)
                missing.append(a)
                continue
            entry["matched"] += 1
            entry["workspace_km"] += (f.get("distance_m") or 0.0)
            if a["id"] in ambiguous_ids:
                entry["ambiguous"] += 1
                continue
            if since and f.get("date") and f["date"] < since:
                entry["before_since"] += 1
                continue
            current, source = f.get("gear_id"), f.get("gear_source")
            if not current:
                entry["to_write"] += 1
                result["assignments"].append({
                    "path": f["path"], "date": f.get("date"), "gear_id": gear_id, "gear_uuid": shoe["uuid"],
                    "replaces_unmapped": source == "garmin_unmapped"})
            elif current == gear_id:
                entry["already"] += 1
            else:
                entry["conflicts"] += 1
                result["conflicts"].append({
                    "path": f["path"], "date": f.get("date"), "kept": current, "kept_source": source or "?",
                    "garmin": gear_id, "garmin_name": shoe["name"]})
        entry["workspace_km"] = _km(entry["workspace_km"])
        entry["missing_from_workspace"] = len(missing)
        for a in missing:
            result["missing_from_workspace"].append({"id": a["id"], "date": a["date"], "uuid": shoe["uuid"],
                                                     "distance_km": _km(a["distance_m"])})

        # --- départ (puce nouvelle seulement) ---
        if entry["status"] in ("new", "out_of_period") and not existing:
            entry["depart_km"], entry["depart_note"] = _depart(
                shoe, acts, missing, entry["matched"], no_id_files, since, info)
            entry["bullet"] = build_bullet(shoe, gear_id, entry["depart_km"])
            result["new_bullets"].append({"uuid": shoe["uuid"], "gear_id": gear_id, "bullet": entry["bullet"],
                                          "date_begin": shoe["date_begin"]})
    for aid in sorted(ambiguous_ids):
        f = by_ws_id.get(aid)
        result["ambiguous"].append({"id": aid, "date": (f or {}).get("date"), "path": (f or {}).get("path"),
                                    "in_workspace": f is not None, "shoes": sorted(claimed[aid])})
    return result


def _depart(shoe, acts, missing, matched, no_id_files, since, info) -> Tuple[Optional[int], str]:
    """`(km | None, explication)` : km Garmin des séances ABSENTES du workspace (voir docstring du module)."""
    if since:
        return None, ("non calculé avec --since : des séances du workspace antérieures à la date seraient "
                      "comptées deux fois (relancer sans --since pour proposer un départ)")
    if info.get("truncated"):
        return None, "non calculé : liste Garmin tronquée (plafond de l'API), total incertain"
    if not acts:
        return None, "aucune séance côté Garmin"
    no_id_days = {f["date"] for f in no_id_files if f.get("date")}
    clash = sorted({a["date"] for a in missing if a["date"] in no_id_days})
    if clash:
        return None, ("non calculé : des fichiers sans garmin_activity_id tombent le même jour qu'une séance "
                      f"Garmin absente ({', '.join(clash[:3])}{'…' if len(clash) > 3 else ''}) — risque de "
                      "double comptage")
    meters = sum(a["distance_m"] for a in missing)
    km = round(meters / 1000.0)
    total = round(sum(a["distance_m"] for a in acts) / 1000.0)
    if km < 1:
        return None, "aucun kilométrage hors workspace"
    return km, (f"{km} km = {len(missing)} séance(s) Garmin de la paire absentes du workspace ; les séances déjà "
                f"dans le workspace ({matched}) ne sont pas recomptées (total Garmin {total} km)")


# ---------------------------------------------------------------------------
# Profil : insertion des puces (pur)
# ---------------------------------------------------------------------------

def _mask_comments(text: str) -> str:
    """Remplace les commentaires HTML par des espaces (mêmes offsets, sauts de ligne conservés)."""
    return re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


_H_CHAUSSURES = re.compile(r"^\s{0,3}#{2,4}[ \t]*chaussures[ \t]*$", re.I | re.M)
_H_MATERIEL_SECTION = re.compile(r"^\s{0,3}##[ \t]+mat[ée]riel\b[^\n]*$", re.I | re.M)
_H_ANY = re.compile(r"^\s{0,3}#{1,6}[ \t]", re.M)
_H_LEVEL1_2 = re.compile(r"^\s{0,3}#{1,2}[ \t]", re.M)
_H_EQUIPMENT_SUB = re.compile(r"^\s{0,3}#{3,4}[ \t]*mat[ée]riel[ \t]*$", re.I | re.M)


def insert_gear_bullets(text: str, bullets: List[str]) -> str:
    """Ajoute `bullets` sous `### Chaussures` sans toucher aux lignes existantes. Sous-section absente :
    créée dans `## Matériel & lieux` (avant `### Matériel` s'il existe, sinon en fin de section) ; section
    `## Matériel & lieux` absente : créée en fin de fichier."""
    if not bullets:
        return text
    if not text.endswith("\n"):
        text += "\n"
    masked = _mask_comments(text)
    block = "\n".join(bullets) + "\n"
    m = _H_CHAUSSURES.search(masked)
    if m:
        after = m.end() + 1
        nxt = _H_ANY.search(masked, after)
        end = nxt.start() if nxt else len(text)
        lines = text[after:end].splitlines(keepends=True)
        last_bullet_end = None
        cursor = after
        for ln in lines:
            cursor += len(ln)
            if re.match(r"^\s*[-*]\s+\S", masked[cursor - len(ln):cursor]):
                last_bullet_end = cursor
        if last_bullet_end is not None:
            return text[:last_bullet_end] + block + text[last_bullet_end:]
        # aucune puce : juste sous le titre (sous d'éventuelles consignes commentées)
        return _splice_after_heading(text, after, end, block)
    sub = "### Chaussures\n\n" + block + "\n"
    sec = _H_MATERIEL_SECTION.search(masked)
    if sec:
        start = sec.end() + 1
        nxt = _H_LEVEL1_2.search(masked, start)
        end = nxt.start() if nxt else len(text)
        eq = _H_EQUIPMENT_SUB.search(masked, start, end)
        if eq:
            return text[:eq.start()] + sub + text[eq.start():]
        body = text[start:end].rstrip("\n")
        insert_at = start + len(body) + (1 if body else 0)
        return text[:insert_at] + "\n" + sub.rstrip("\n") + "\n" + text[insert_at:]
    sep = "" if text.endswith("\n\n") else "\n"
    return text + sep + "## Matériel & lieux\n\n" + sub.rstrip("\n") + "\n"


def _splice_after_heading(text: str, after: int, end: int, block: str) -> str:
    body = text[after:end]
    stripped = body.rstrip("\n")
    tail = body[len(stripped):]              # lignes vides finales, conservées avant le titre suivant
    lead = "" if stripped else "\n"
    joined = stripped + ("\n" if stripped else "") + lead + block
    return text[:after] + joined + (tail if tail else ("\n" if end < len(text) else "")) + text[end:]


# ---------------------------------------------------------------------------
# Bloc `arc` d'une activité : écriture textuelle minimale (pur)
# ---------------------------------------------------------------------------

def set_block_keys(text: str, updates: Dict[str, Any]) -> str:
    """Ajoute/remplace des clés de premier niveau du bloc ```arc SANS reformater le reste : insertion
    textuelle avant l'accolade finale (ordre et mise en forme conservés, ligne unique ou multi-lignes).
    Une clé déjà présente (ex. `gear_source: "garmin_unmapped"`) réécrit le bloc en JSON, indentation
    d'origine conservée."""
    m = C.BLOCK_RE.search(text)
    if not m:
        raise C.ContractError("bloc ```arc absent")
    body = m.group(1)
    data = json.loads(body)
    expected = dict(data)
    expected.update(updates)
    multiline = "\n" in body
    if any(k in data for k in updates):
        data.update(updates)
        if multiline:
            indent_m = re.search(r"\n([ \t]+)\S", body)
            new_body = json.dumps(data, ensure_ascii=False, indent=len(indent_m.group(1)) if indent_m else 2)
        else:
            new_body = json.dumps(data, ensure_ascii=False, separators=(", ", ": "))
    else:
        close = body.rstrip().rfind("}")
        before = body[:close].rstrip()
        items = [f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in updates.items()]
        if multiline:
            last_line = before.rsplit("\n", 1)[-1]
            indent = re.match(r"[ \t]*", last_line).group(0) or "  "
            new_body = before + ",\n" + ",\n".join(indent + it for it in items) + "\n" + body[close:].rstrip()
        else:
            new_body = before + ", " + ", ".join(items) + "}"
    if json.loads(new_body) != expected:
        raise C.ContractError("réécriture du bloc ```arc non conforme à l'attendu")
    return text[:m.start(1)] + new_body + text[m.end(1):]


# ---------------------------------------------------------------------------
# Workspace (E/S locales)
# ---------------------------------------------------------------------------

def scan_workspace(workspace: Path) -> List[dict]:
    """Une entrée par `activities/*.md` (niveau supérieur seulement) portant un bloc `activity`."""
    out = []
    folder = workspace / "activities"
    for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        rel = f"activities/{path.name}"
        entry = {"path": rel, "date": L.filename_date(path.name), "garmin_activity_id": None,
                 "distance_m": 0.0, "gear_id": None, "gear_source": None, "has_block": False}
        try:
            block = C.extract_block(path.read_text(encoding="utf-8", errors="replace"))
        except C.ContractError:
            block = None
        if block and block.get("kind") == "activity":
            entry["has_block"] = True
            entry["date"] = block.get("date") or entry["date"]
            aid = block.get("garmin_activity_id")
            entry["garmin_activity_id"] = int(aid) if isinstance(aid, int) and not isinstance(aid, bool) else None
            entry["distance_m"] = float(block.get("distance_m") or 0)
            entry["gear_id"] = block.get("gear_id") or None
            entry["gear_source"] = block.get("gear_source") or None
        elif block is not None:
            continue   # autre type de bloc dans activities/ : ni séance ni « fichier sans identifiant »
        out.append(entry)
    return out


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp-gearbackfill")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def apply_plan(workspace: Path, profile: Path, result: dict, *, validate=None) -> dict:
    """Écrit puces puis `gear_id` ; chaque fichier est validé, restauré tel quel en cas d'échec."""
    if validate is None:
        import arc_index
        validate = arc_index.validate_file
    out: Dict[str, Any] = {"profile_written": False, "written": [], "failed": [], "skipped": []}
    if result["new_bullets"]:
        original = profile.read_text(encoding="utf-8")
        updated = insert_gear_bullets(original, [b["bullet"] for b in result["new_bullets"]])
        _atomic_write(profile, updated)
        parsed = {g.get("garmin_uuid"): g["gear_id"] for g in L.parse_gear(updated)}
        bad = [b["uuid"] for b in result["new_bullets"] if parsed.get(b["uuid"]) != b["gear_id"]]
        if bad:
            _atomic_write(profile, original)
            out["failed"].append({"path": str(profile.relative_to(workspace)) if profile.is_relative_to(workspace)
                                  else str(profile), "error": "puces non relues après écriture — profil restauré"})
            return out
        out["profile_written"] = True
    for a in result["assignments"]:
        path = workspace / a["path"]
        original = path.read_text(encoding="utf-8")
        try:
            block = C.extract_block(original) or {}
            if block.get("gear_id"):
                out["skipped"].append({"path": a["path"], "reason": "gear_id apparu depuis la simulation"})
                continue
            updated = set_block_keys(original, {"gear_id": a["gear_id"], "gear_source": "garmin"})
            _atomic_write(path, updated)
            ok, errors, _warnings = validate(path)
            if not ok:
                raise C.ContractError("; ".join(errors) or "validation refusée")
        except (C.ContractError, OSError, ValueError) as exc:
            _atomic_write(path, original)
            out["failed"].append({"path": a["path"], "error": str(exc)})
            continue
        out["written"].append(a["path"])
    return out


def reindex(workspace: Path) -> dict:
    import arc_index
    conn = arc_index.open_db(workspace)
    try:
        counts = arc_index.index_workspace(conn, workspace)
        gear = arc_index.gear_mileage(conn)
    finally:
        conn.close()
    return {"index": counts, "gear": gear}


# ---------------------------------------------------------------------------
# Client Garmin (E/S ; garminconnect importé paresseusement)
# ---------------------------------------------------------------------------

class GarminSource:
    """Adaptateur mince : inventaire, séances d'une paire (avec pagination quand l'API le permet)."""

    def __init__(self, client):
        self.client = client

    def profile_id(self):
        return self.client.get_device_last_used().get("userProfileNumber")

    def gear(self) -> List[dict]:
        return self.client.get_gear(self.profile_id()) or []

    def defaults(self) -> List[dict]:
        try:
            return self.client.get_gear_defaults(self.profile_id()) or []
        except Exception:
            return []

    def gear_activities(self, uuid: str) -> dict:
        """`{"activities": [...], "error": str|None, "truncated": bool}`. `get_gear_activities` n'a pas de
        décalage (`start`) : au plafond de 1000, on pagine par `connectapi` quand le client l'expose,
        sinon la liste est déclarée tronquée (jamais un total présenté comme complet)."""
        try:
            raw = list(self.client.get_gear_activities(uuid, limit=GEAR_ACTIVITIES_PAGE) or [])
        except Exception as exc:   # noqa: BLE001 — une paire injoignable ne doit pas arrêter le rapport
            return {"activities": [], "error": f"{type(exc).__name__}: {exc}", "truncated": False}
        truncated = False
        if len(raw) >= GEAR_ACTIVITIES_PAGE:
            base = getattr(self.client, "garmin_connect_activities_baseurl", None)
            fetch = getattr(self.client, "connectapi", None)
            if base and fetch:
                start = len(raw)
                try:
                    while True:
                        page = fetch(f"{base}{uuid}/gear?start={start}&limit={GEAR_ACTIVITIES_PAGE}") or []
                        raw.extend(page)
                        if len(page) < GEAR_ACTIVITIES_PAGE:
                            break
                        start += len(page)
                except Exception:   # noqa: BLE001
                    truncated = True
            else:
                truncated = True
        return {"activities": normalize_gear_activities(raw), "error": None, "truncated": truncated}


class FakeClient:
    """Client de test (`--fake-client fichier.json`, option cachée) : aucun réseau, aucun jeton."""

    def __init__(self, spec: dict):
        self.spec = spec

    def get_device_last_used(self):
        return {"userProfileNumber": self.spec.get("profile_id", 1)}

    def get_gear(self, _pid):
        return self.spec.get("gear", [])

    def get_gear_defaults(self, _pid):
        return self.spec.get("defaults", [])

    def get_gear_activities(self, uuid, limit=1000):
        value = self.spec.get("gear_activities", {}).get(uuid, [])
        if isinstance(value, str):
            raise RuntimeError(value)
        return value[:limit]


def _auto_relaunch(argv: List[str]) -> None:
    """Relance avec le python de garmin-mcp quand `garminconnect` manque (comme `download_fit.py`)."""
    try:
        import garminconnect  # noqa: F401
        return
    except ImportError:
        pass
    candidates: List[str] = []
    if os.environ.get("GARMIN_PYTHON"):
        candidates.append(os.path.expanduser(os.environ["GARMIN_PYTHON"]))
    exe = shutil.which("garmin-mcp")
    if exe:
        real = os.path.realpath(exe)
        candidates += [os.path.join(os.path.dirname(real), n) for n in ("python3", "python")]
    candidates.append(os.path.expanduser("~/.local/share/uv/tools/garmin-mcp/bin/python3"))
    for py in candidates:
        if os.path.exists(py) and os.path.realpath(py) != os.path.realpath(sys.executable):
            sys.exit(subprocess.run([py, os.path.abspath(__file__)] + argv).returncode)
    print("ERREUR : module 'garminconnect' introuvable dans cet interpréteur.\n"
          "→ utilisez le python de garmin-mcp : GARMIN_PYTHON=~/.local/share/uv/tools/garmin-mcp/bin/python3",
          file=sys.stderr)
    sys.exit(EXIT_USAGE)


def connect_garmin(token_dir: Path):
    """Client `garminconnect` authentifié par les jetons locaux (aucun mot de passe)."""
    from garminconnect import Garmin   # import paresseux : dépendance non standard documentée
    client = Garmin()
    try:
        client.login(str(token_dir))
    except TypeError:
        client.login()
    return client


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

_STATUS_LABEL = {
    "new": "puce à ajouter", "existing": "puce existante (id réutilisé)", "ignored": "(ignorée) — jamais attribuée",
    "out_of_period": "hors période du workspace", "error": "erreur Garmin",
    "duplicate_in_profile": "uuid dupliqué dans le profil",
}


def render_report(result: dict, applied: Optional[dict] = None, reindexed: Optional[dict] = None) -> str:
    lo, hi = result["workspace_period"]
    lines = [("RATTRAPAGE DU MATÉRIEL GARMIN — " + ("application" if applied is not None else "simulation (rien n'est écrit)")),
             f"Workspace : {result['workspace_files']} fichier(s) d'activité, {result['workspace_with_id']} avec "
             f"garmin_activity_id, période {lo or '?'} → {hi or '?'}"
             + (f" ; --since {result['since']}" if result["since"] else ""), ""]
    shown = [s for s in result["shoes"] if s["status"] not in ("out_of_period",) or result["all_shoes"]]
    hidden = [s for s in result["shoes"] if s not in shown]
    lines.append(f"PAIRES ({len(shown)} retenue(s)" + (f", {len(hidden)} hors période masquée(s) — --all-shoes pour les proposer" if hidden else "") + ")")
    for s in shown:
        lines.append(f"- {s['name']} [{_STATUS_LABEL.get(s['status'], s['status'])}]"
                     + (" (retirée)" if s["retired"] else ""))
        if s["status"] == "error":
            lines.append(f"    erreur : {s['error']}")
            continue
        if s["bullet"]:
            lines.append(f"    puce proposée : {s['bullet']}")
        elif s["gear_id"]:
            lines.append(f"    gear_id : {s['gear_id']}")
        lines.append(f"    séances rattachées : {s['matched']} (à écrire {s['to_write']}, déjà attribuées "
                     f"{s['already']}, conflits {s['conflicts']}, ambiguës {s['ambiguous']}"
                     + (f", avant --since {s['before_since']}" if s['before_since'] else "") + ")")
        lines.append(f"    km : {s['workspace_km']:g} dans le workspace · {s['garmin_km']:g} au total chez Garmin "
                     f"({s['garmin_sessions']} séance(s))" + (" — LISTE TRONQUÉE" if s["truncated"] else ""))
        if s["depart_note"]:
            lines.append(f"    départ : {s['depart_note']}")
    if result["garmin_defaults"]:
        lines += ["", "PAIRES PAR DÉFAUT CHEZ GARMIN (non reprises : `(par défaut)` n'est jamais posé automatiquement) : "
                  + ", ".join(result["garmin_defaults"])]
    for title, items, fmt in (
        ("CONFLITS — déclaration déjà présente conservée (priorité athlète/chat)", result["conflicts"],
         lambda c: f"- {c['path']} : garde « {c['kept']} » ({c['kept_source']}), Garmin indique « {c['garmin']} » ({c['garmin_name']})"),
        ("AMBIGUËS — revendiquées par deux paires chez Garmin, jamais attribuées", result["ambiguous"],
         lambda a: f"- activité {a['id']} ({a['date'] or '?'}){'' if a['in_workspace'] else ' hors workspace'} : {len(a['shoes'])} paires"),
    ):
        if items:
            lines += ["", f"{title} ({len(items)})"] + [fmt(i) for i in items[:20]]
            if len(items) > 20:
                lines.append(f"  … et {len(items) - 20} autre(s) (voir --json)")
    miss = result["missing_from_workspace"]
    if miss:
        lines += ["", f"SÉANCES GARMIN ABSENTES DU WORKSPACE ({len(miss)}, {sum(m['distance_km'] for m in miss):.0f} km) — "
                  "comptées dans « départ » des puces nouvelles, jamais réimportées ici"]
    if result["workspace_without_id"]:
        lines += ["", f"FICHIERS SANS garmin_activity_id : {len(result['workspace_without_id'])} — non rattachables "
                  "automatiquement (déclarer la paire dans le chat)"]
    total_write = len(result["assignments"])
    lines += ["", f"BILAN : {len(result['new_bullets'])} puce(s) à ajouter, {total_write} séance(s) à renseigner, "
              f"{len(result['conflicts'])} conflit(s), {len(result['ambiguous'])} ambiguë(s)."]
    if applied is None:
        lines.append("Simulation seulement. Pour écrire : relancer avec --apply.")
    else:
        lines.append(f"Appliqué : profil {'mis à jour' if applied['profile_written'] else 'inchangé'}, "
                     f"{len(applied['written'])} séance(s) écrite(s), {len(applied['failed'])} échec(s), "
                     f"{len(applied['skipped'])} ignorée(s).")
        for f in applied["failed"]:
            lines.append(f"  échec : {f['path']} — {f['error']}")
        if reindexed:
            lines.append(f"Index reconstruit : {reindexed['index']}.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", help="racine du workspace (sinon ARC_WORKSPACE / défaut du moteur)")
    p.add_argument("--apply", action="store_true", help="écrit (sinon simulation)")
    p.add_argument("--since", metavar="AAAA-MM-JJ", help="ne renseigne que les séances du workspace à partir de cette date")
    p.add_argument("--gear", metavar="UUID", help="une seule paire Garmin")
    p.add_argument("--all-shoes", action="store_true",
                   help="propose aussi les paires sans séance dans la période du workspace (puces `(retirée)`)")
    p.add_argument("--json", action="store_true", help="sortie machine")
    p.add_argument("--tokens-dir", help="répertoire des jetons Garmin (défaut : résolution de coach_doctor)")
    p.add_argument("--fake-client", help=argparse.SUPPRESS)   # tests : JSON d'un client simulé, aucun réseau
    return p


def _profile_path(workspace: Path) -> Path:
    import arc_index
    try:
        rel = arc_index.load_config(workspace).get("athlete", {}).get("profile") or DEFAULT_PROFILE_REL
    except Exception:   # noqa: BLE001 — TOML invalide : le doctor le signale, défaut ici
        rel = DEFAULT_PROFILE_REL
    return workspace / rel


def run(args, source=None) -> Tuple[int, dict, str]:
    """Cœur testable : `(code, charge JSON, rapport texte)`. `source` = `GarminSource` (injectable)."""
    from coach_setup import workspace_root
    workspace = workspace_root(args.workspace)
    if args.since:
        try:
            date.fromisoformat(args.since)
        except ValueError:
            return EXIT_USAGE, {"error": "--since"}, f"--since : date AAAA-MM-JJ attendue, « {args.since} » reçue."
    profile = _profile_path(workspace)
    profile_text = profile.read_text(encoding="utf-8") if profile.is_file() else ""
    if args.apply and not profile.is_file():
        return EXIT_NO_PROFILE, {"error": "profile_missing"}, (
            f"Profil athlète introuvable ({profile}) : lancez /coach-setup avant --apply.")
    if source is None:
        return EXIT_USAGE, {"error": "no_source"}, "aucune source Garmin"
    try:
        shoes = normalize_shoes(source.gear())
    except Exception as exc:   # noqa: BLE001
        return EXIT_USAGE, {"error": "garmin"}, f"Garmin injoignable : {type(exc).__name__}: {exc}"
    wanted = [s for s in shoes if not args.gear or s["uuid"] == args.gear.strip().lower()]
    if args.gear and not wanted:
        return EXIT_USAGE, {"error": "gear_not_found"}, f"--gear : aucune chaussure Garmin d'uuid {args.gear}."
    gear_acts = {s["uuid"]: source.gear_activities(s["uuid"]) for s in wanted}
    ws_files = scan_workspace(workspace)
    equipment_ids = {e["gear_id"] for e in L.parse_equipment(profile_text)} if profile_text else set()
    shoe_names = {s["uuid"]: s["name"] for s in shoes}
    default_names = sorted({shoe_names.get(str(d.get("uuid") or "").lower(), "") for d in source.defaults()} - {""})
    result = plan(shoes, gear_acts, ws_files, L.parse_gear(profile_text) if profile_text else [],
                  since=args.since, only_gear=args.gear, all_shoes=args.all_shoes,
                  extra_used_ids=equipment_ids, garmin_defaults=default_names)
    code, applied, reindexed = EXIT_OK, None, None
    if any(s["status"] == "error" for s in result["shoes"]):
        code = EXIT_PARTIAL
    if args.apply:
        applied = apply_plan(workspace, profile, result)
        if applied["failed"]:
            code = EXIT_PARTIAL
        reindexed = reindex(workspace)
    payload = {"dry_run": not args.apply, "workspace": str(workspace), **result}
    if applied is not None:
        payload["applied"] = applied
        payload["reindexed"] = reindexed
    return code, payload, render_report(result, applied, reindexed)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.fake_client:
        source = GarminSource(FakeClient(json.loads(Path(args.fake_client).read_text(encoding="utf-8"))))
    else:
        _auto_relaunch(sys.argv[1:] if argv is None else list(argv))
        from coach_doctor import resolve_tokens_dir
        from coach_setup import workspace_root
        tokens = resolve_tokens_dir(args.tokens_dir, workspace_root(args.workspace))
        print("Connexion à Garmin Connect (jusqu'à ~2 min)…", file=sys.stderr)
        try:
            source = GarminSource(connect_garmin(tokens))
        except Exception as exc:   # noqa: BLE001
            print(f"Authentification Garmin impossible ({type(exc).__name__}: {exc}). Vérifiez {tokens} "
                  "(/coach-doctor).", file=sys.stderr)
            return EXIT_USAGE
    code, payload, report = run(args, source)
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else report)
    return code


if __name__ == "__main__":
    sys.exit(main())
