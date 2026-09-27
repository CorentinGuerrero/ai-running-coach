#!/usr/bin/env python3
"""Génère les commandes Gemini CLI depuis `agents/*.md` et les skills-commandes.

Chaque prompt d'agent existait jusqu'ici en double : `agents/<nom>.md` et
`config/gemini/commands/<nom>.toml`, recopié à la main. Les deux avaient déjà
divergé (la copie Gemini du coach prescrivait `leanproxy_invoke_tool(...)` là où
l'agent parle de l'outil direct) et `course-strategist` n'avait aucune commande.

`agents/` est la source de vérité pour les commandes d'agent. Un skill peut
aussi devenir une commande Gemini de premier niveau (ex. `/today`, `/why`,
`/week`, `/race`, #66) en portant `gemini_command: "true"` dans son
frontmatter — c'est le seul signal utilisé ici, aucune liste à maintenir à
côté : un skill qui n'est qu'un outil interne (chargé par un agent, jamais
tapé directement) n'a pas ce champ et n'obtient pas de commande.

`agents/` et les skills marqués sont donc la source de vérité ; ce script
produit l'autre surface.

    python3 scripts/build-gemini-commands.py            # (ré)génère
    python3 scripts/build-gemini-commands.py --check    # échoue si obsolète (CI)

Bibliothèque standard uniquement (CONTRIBUTING.md).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO / "agents"
SKILLS_DIR = REPO / "skills"
OUTPUT_DIR = REPO / "config" / "gemini" / "commands"

HEADER_AGENT = "# Généré par scripts/build-gemini-commands.py — NE PAS ÉDITER À LA MAIN.\n# Source : agents/{name}.md\n"
HEADER_SKILL = "# Généré par scripts/build-gemini-commands.py — NE PAS ÉDITER À LA MAIN.\n# Source : skills/{name}/SKILL.md\n"
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


class GenerationError(RuntimeError):
    pass


def parse_frontmatter(path: Path) -> tuple:
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        raise GenerationError(f"{path} : frontmatter YAML absent.")
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("name", "description"):
        if key not in fields:
            raise GenerationError(f"{path} : frontmatter sans « {key} ».")
    return fields, match.group(2).strip()


def parse_agent(path: Path) -> tuple:
    fields, body = parse_frontmatter(path)
    return fields["name"], fields["description"], body


def command_skill_files() -> list:
    """Skills qui sont aussi des commandes de premier niveau (`gemini_command: "true"`).

    Un skill sans frontmatter valide (ou sans `name`/`description`) est déjà
    signalé par `tests/lint/test_prompt_lint.py::TestSkillFrontmatter` — pas la
    responsabilité de CE scan, qui ne cherche qu'un signal optionnel parmi tous
    les skills : le laisser lever ferait échouer la génération Gemini pour un
    problème sans rapport avec elle, sur un skill qui ne demande même pas de
    commande."""
    found = []
    for path in SKILLS_DIR.glob("*/SKILL.md"):
        try:
            fields, _ = parse_frontmatter(path)
        except GenerationError:
            continue
        if fields.get("gemini_command", "").lower() == "true":
            found.append(path)
    return sorted(found)


def parse_skill_command(path: Path) -> tuple:
    fields, body = parse_frontmatter(path)
    return fields["name"], fields["description"], body


def toml_basic_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render(name: str, description: str, body: str, header: str) -> str:
    # Chaîne littérale multi-ligne ('''…'''), sans séquences d'échappement : les
    # prompts contiennent des antislashs (JSON, regex) qu'une chaîne "…" mangerait.
    if "'''" in body:
        raise GenerationError(
            f"{name} contient ''' — incompatible avec une chaîne littérale TOML."
        )
    return (
        header.format(name=name)
        + f"description = {toml_basic_string(description)}\n"
        + "prompt = '''\n"
        + body
        + "\n\n---\n"
        + "Demande de l'utilisateur : {{args}}\n"
        + "'''\n"
    )


def build() -> dict:
    agents = sorted(AGENTS_DIR.glob("*.md"))
    if not agents:
        raise GenerationError(f"aucun agent trouvé dans {AGENTS_DIR}")
    commands = {
        f"{name}.toml": render(name, description, body, HEADER_AGENT)
        for name, description, body in (parse_agent(p) for p in agents)
    }
    for skill_path in command_skill_files():
        name, description, body = parse_skill_command(skill_path)
        filename = f"{name}.toml"
        if filename in commands:
            raise GenerationError(
                f"{skill_path} : nom « {name} » entre en collision avec une commande d'agent."
            )
        commands[filename] = render(name, description, body, HEADER_SKILL)
    return commands


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="vérifie sans écrire")
    args = parser.parse_args(argv)

    try:
        expected = build()
    except GenerationError as exc:
        print(f"build-gemini-commands: {exc}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stale, written = [], []

    for filename, content in expected.items():
        target = OUTPUT_DIR / filename
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current == content:
            continue
        if args.check:
            stale.append(filename + (" (absent)" if current is None else " (obsolète)"))
        else:
            target.write_text(content, encoding="utf-8")
            written.append(filename)

    for orphan in sorted(OUTPUT_DIR.glob("*.toml")):
        if orphan.name not in expected:
            if args.check:
                stale.append(orphan.name + " (agent supprimé)")
            else:
                orphan.unlink()
                written.append(orphan.name + " (supprimé)")

    if args.check:
        if stale:
            print("Commandes Gemini obsolètes : " + ", ".join(stale), file=sys.stderr)
            print("Relancez : python3 scripts/build-gemini-commands.py", file=sys.stderr)
            return 1
        print(f"{len(expected)} commande(s) Gemini à jour.")
        return 0

    print(f"{len(expected)} commande(s) générée(s)" + (f" ; modifiées : {', '.join(written)}" if written else " ; aucune modification"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
