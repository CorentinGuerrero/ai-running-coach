# 🚀 Démarrage rapide

Ce guide vous permet d'installer et de configurer `ai-running-coach` en quelques minutes.

## Prérequis

- **macOS** ou **Linux**
- **bash 3.2+** (celui livré avec macOS convient)
- **curl** et **git**
- Un compte **Garmin Connect** (avec un appareil Garmin)

!!! tip "Homebrew"
    **Homebrew** est recommandé sur macOS. Il est requis uniquement pour le mode passerelle optionnel (`leanproxy-mcp`).

## Installation

```bash
git clone https://github.com/mmornati/ai-running-coach.git
cd ai-running-coach
./install.sh
```

Le script effectue les étapes suivantes :

1. **uv** — gestionnaire Python (installé si absent)
2. **garmin-mcp** — serveur MCP d'accès à Garmin Connect
3. **garmin-mcp-auth** — authentification Garmin (tokens valides ~6 mois)
4. **Configuration IDE** — serveur MCP `garmin` (mode direct, liste blanche d'outils) pour Claude Code, GitHub Copilot, OpenCode, Gemini CLI, Cursor, Windsurf
5. **Dossiers de travail** — `activities/`, `medical/`, `nutrition/`, `planning/`, `rapports/`, `resources/`

## Authentification Garmin

Lors de la première installation, le script lance l'authentification Garmin Connect :

1. Saisissez votre **email** et **mot de passe** Garmin Connect
2. Validez le **code MFA** si votre compte en est équipé
3. Les tokens sont stockés dans `~/.garminconnect/` (valides ~6 mois)

!!! warning "Sécurité"
    Vos identifiants ne sont jamais stockés dans le projet. Les tokens sont conservés dans votre répertoire personnel (`~/.garminconnect/`), hors du dépôt.

## Options du script

| Option | Description |
|---|---|
| `--preset NOM` | Préréglage qui compose les options ci-dessous : `laptop`, `coach-server` ou `docker` — voir [Préréglages](#prereglages---preset) |
| `--ide claude` | Installe pour un IDE précis (`claude`, `copilot`, `opencode`, `gemini`, `cursor`, `windsurf`) |
| `--agents LISTE` | Staff à installer, ex. `coach,nutritionist` — voir [Configuration](configuration.md#le-staff-agents) |
| `--no-medical` | Tous les agents sauf le médecin |
| `--no-auth` | Saute l'authentification Garmin |
| `--use-leanproxy` | Mode passerelle leanproxy-mcp (power user, optionnel) |
| `--workspace DIR` | Données et configs IDE dans `DIR` (votre dépôt privé), moteur lié — voir [Votre workspace privé](workspace.md) |
| `--daily-sync` | Synchronisation Garmin automatique (cron/launchd) + notification — voir [Le coach dans la poche](mobile.md) |
| `--remote-control` | Service Claude Code Remote Control : le coach depuis le téléphone — voir [Le coach dans la poche](mobile.md) |
| `--dry-run` | Affiche les actions sans rien exécuter |
| `--help` | Affiche l'aide |

## Préréglages (`--preset`)

Un préréglage ne fait que **composer les options ci-dessus** — jamais de
comportement qui ne serait pas atteignable avec les options existantes. Une
option passée explicitement l'emporte toujours sur le préréglage, quel que
soit son ordre sur la ligne de commande (`--preset laptop --daily-sync`
revient exactement à `--daily-sync --preset laptop`).

| Préréglage | Équivaut à | Pour qui |
|---|---|---|
| `laptop` | `--ide all` (le reste aux valeurs par défaut) | Le parcours de cette page : votre propre machine, en interactif, tous les IDE supportés. |
| `coach-server` | `--ide claude --daily-sync --remote-control` | La machine « coach » toujours allumée de [Le coach dans la poche](mobile.md) : synchronisation automatique + dialogue depuis le téléphone. |
| `docker` | `--ide claude --daily-sync --no-auth` | La machine qui sert le [tableau de bord en conteneur](dashboard/docker.md) derrière un reverse proxy : le conteneur ne parle jamais à Garmin (workspace monté en lecture seule), donc pas d'authentification interactive à l'installation ; `--daily-sync` garde les données du workspace monté à jour ; pas de Remote Control, l'interface de cette machine est le tableau de bord web. |

Avant d'agir, le script affiche un récapitulatif de la configuration
effective, en indiquant pour chaque option si sa valeur vient du préréglage
ou d'une option explicite :

```bash
./install.sh --preset coach-server --no-auth --dry-run
```

```
==> Récapitulatif de la configuration effective :
  Préréglage             coach-server
  IDE                    claude       (préréglage coach-server)
  Auth Garmin            sautée       (explicite)
  Sync auto (cron)       oui          (préréglage coach-server)
  Remote Control         oui          (préréglage coach-server)
  ...
```

`--dry-run` fonctionne avec chaque préréglage (aucune écriture sur le
disque) ; un nom de préréglage inconnu est une erreur claire (`Préréglage
inconnu : « … ». Valides : laptop coach-server docker`), pas un plantage.

## Premiers pas

1. **Lancez votre IDE** dans le dossier du projet

2. **Lancez `/coach-setup`**

    Un entretien court : votre staff d'agents, votre discipline, la façon dont le
    coach vous parle, votre bilan santé matinal. Il installe aussi votre profil
    d'athlète et votre fiche d'objectif.

    Relancer la commande est sans risque : elle ne pose que les questions sans
    réponse et ne remplace jamais un réglage existant.
    Voir [Premier démarrage](skills/coach-setup.md) et [Configuration](configuration.md).

3. **Demandez à l'agent `coach`** de définir votre objectif, par exemple :

    - *« Je veux préparer un trail de 50 km avec 2500 m de D+ dans 6 mois »*
    - *« Aide-moi à planifier ma semaine d'entraînement »*

4. L'agent `coach` coordonne les agents que vous avez retenus et pousse vos séances directement dans le **calendrier Garmin Connect**

## Vérification

Pour vérifier que tout est bien installé :

```bash
uv --version
garmin-mcp --version
ls ~/.garminconnect/
```

En mode passerelle (`--use-leanproxy`), vérifiez aussi `leanproxy-mcp --version`.

## Prochaines étapes

- [Configuration](configuration.md) — staff, style de coaching, discipline, bilan santé
- [Configuration Garmin](garmin-setup.md) — détails sur l'accès Garmin
- [Les agents](agents.md) — comprendre le rôle de chaque agent
- [Les skills](skills.md) — découvrir les skills disponibles
- [Dépannage](troubleshooting.md) — résoudre les problèmes courants
