# Configuration Garmin

Cette page détaille l'accès à **Garmin Connect** utilisé par `ai-running-coach`.

## Architecture

### Mode direct (défaut)

```mermaid
flowchart LR
    A["Votre IDE<br/>(agent IA)"] --> B["garmin-mcp<br/>(serveur, liste blanche)"]
    B --> C["Garmin Connect<br/>(API)"]
```

### Mode passerelle (optionnel — power user)

```mermaid
flowchart LR
    A["Votre IDE<br/>(agent IA)"] --> B["leanproxy-mcp<br/>(passerelle)"]
    B --> C["garmin-mcp<br/>(serveur)"]
    C --> D["Garmin Connect<br/>(API)"]
```

- **`garmin-mcp`** — serveur MCP qui expose les données Garmin Connect (activités, santé, sommeil, calendrier, planification d'entraînements). **Mode direct par défaut** : il est enregistré directement dans votre IDE avec une **liste blanche d'outils** (`GARMIN_ENABLED_TOOLS`) pour réduire la taxe de contexte (~151 outils → ~25).
- **`leanproxy-mcp`** — passerelle MCP optionnelle (mode *power user*) qui agrège les serveurs, charge les schémas à la demande et économise ~98 % de tokens. Installée avec `--use-leanproxy`.
- **`garmin-mcp-auth`** — outil d'authentification OAuth (tokens stockés dans `~/.garminconnect/`)

## Composants installés

| Composant | Rôle | Installation |
|---|---|---|
| `uv` | Gestionnaire Python | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `garmin-mcp` | Serveur MCP Garmin | `uv tool install --python 3.12 git+https://github.com/Taxuspt/garmin_mcp@cfc5d799ab0f165e837f1188a1d093c65838aaf7` |
| `garmin-mcp-auth` | Authentification OAuth | via `uv run garmin-mcp-auth` |
| `leanproxy-mcp` | Passerelle MCP (optionnel) | `brew tap mmornati/leanproxy-mcp && brew install leanproxy-mcp` |

## Mode direct (défaut)

Le script d'installation enregistre le serveur MCP `garmin` dans votre IDE avec la liste blanche d'outils :

```json
{
  "mcpServers": {
    "garmin": {
      "command": "garmin-mcp",
      "args": ["stdio"],
      "env": {
        "GARMIN_ENABLED_TOOLS": "get_activities,get_activities_by_date,get_activity,get_activity_fit_data,get_activity_splits,get_activity_typed_splits,get_activity_split_summaries,get_sleep_data,get_hrv_data,get_rhr_day,get_training_readiness,get_calendar_events,get_courses,get_workouts,get_workout_by_id,get_scheduled_workouts,schedule_workouts,schedule_week,upload_workout,upload_course,create_strength_workout,delete_workout,unschedule_workout,unschedule_workouts,download_activity_file,get_stats,get_lactate_threshold,get_training_status,get_gear,get_activity_gear,add_gear_to_activity"
      }
    }
  }
}
```

!!! tip "Pourquoi une liste blanche ?"
    `garmin-mcp` expose ~151 outils. Les agents de ce projet n'en utilisent qu'une vingtaine. La liste blanche (`GARMIN_ENABLED_TOOLS`) réduit fortement la taxe de contexte de chaque requête. Vous pouvez l'ajuster dans `install.sh` (variable `GARMIN_TOOL_WHITELIST`).

## Mode passerelle (optionnel — power user)

Installez avec `--use-leanproxy` :

```bash
./install.sh --use-leanproxy
```

Le script configure deux fichiers dans `~/.config/leanproxy/` :

### `config.yaml`

```yaml
server:
  host: "127.0.0.1"
  port: 8080
  timeout: 300s
  max_batch_size: 100
optimization:
  lazy_loading:
    enabled: true
    stub_tokens: 54
    cache_ttl: 24h
namespaces:
  sport:
    description: "Sport tools"
    servers:
      - garmin
    allowed_clients:
      - "*"
logging:
  level: "info"
  file: ""
```

### `leanproxy_servers.yaml`

```yaml
version: "1.0"
servers:
    - name: garmin
      enabled: true
      transport: stdio
      stdio:
        command: garmin-mcp
        args:
            - stdio
        env:
            - GARMIN_ENABLED_TOOLS: "get_activities,get_activities_by_date,get_activity,get_activity_fit_data,get_activity_splits,get_activity_typed_splits,get_activity_split_summaries,get_sleep_data,get_hrv_data,get_rhr_day,get_training_readiness,get_calendar_events,get_courses,get_workouts,get_workout_by_id,get_scheduled_workouts,schedule_workouts,schedule_week,upload_workout,upload_course,create_strength_workout,delete_workout,unschedule_workout,unschedule_workouts,download_activity_file,get_stats,get_lactate_threshold,get_training_status,get_gear,get_activity_gear,add_gear_to_activity"
        cwd: .
      timeout: 300s
      connect_timeout: 10s
      idle_timeout: ""
```

!!! note "Config existante"
    Le script **ne remplace pas** une configuration existante. Si `config.yaml` ou `leanproxy_servers.yaml` existent déjà, ils sont conservés.

!!! warning "Liste blanche déjà installée avant un ajout d'outil"
    Conséquence directe de la note ci-dessus : une installation leanproxy déjà
    en place ne reçoit **pas automatiquement** un outil ajouté plus tard à
    `GARMIN_TOOL_WHITELIST` (ex. `get_stats`/`get_lactate_threshold`/
    `get_training_status`, story #65) — `~/.config/leanproxy_servers.yaml`
    n'est réécrit que s'il est absent. Éditez sa ligne `GARMIN_ENABLED_TOOLS`
    à la main pour y ajouter le nouvel outil, plutôt que de réinstaller :

    ```bash
    grep -n GARMIN_ENABLED_TOOLS ~/.config/leanproxy_servers.yaml
    # ajoutez le(s) nouveau(x) outil(s) à la fin de la liste, séparés par une virgule
    ```

    Appelez ensuite les nouveaux outils via
    `leanproxy_invoke_tool(server="garmin", tool="get_stats", arguments={...})`
    (voir `skills/garmin-sync-efficiency/SKILL.md`), pas directement.

## Synchronisation du matériel Garmin

Garmin Connect gère son propre matériel (attribution automatique par sport, seuils de retraite).
Trois outils sont dans la liste blanche : `get_gear` et `get_activity_gear` (lecture) et
`add_gear_to_activity` (**écriture** côté Garmin — le coach ne l'appelle qu'après votre
confirmation explicite dans la conversation, jamais en synchronisation automatique).

- **Association, une seule fois.** Au premier `get_gear` qui montre un matériel Garmin sans puce
  correspondante, le coach vous propose, pour chacun, de l'associer à une puce existante de
  `### Chaussures` (ajout du segment `garmin: <uuid>`) ou d'en créer une (`alerte` ← seuil Garmin,
  `depuis` ← date de début, `(retirée)` ← statut retiré). Jamais d'association devinée ; sans
  réponse, le matériel n'est simplement pas attribué. Le total Garmin d'une paire qui précède
  votre suivi peut alimenter son `départ` (départ = total Garmin − kilomètres déjà comptés par vos
  séances, jamais négatif : aucun double comptage).
- **Priorité d'attribution.** Votre déclaration en chat > matériel attaché par la montre
  à la séance (un seul `get_activity_gear` par séance **nouvelle**) > `(par défaut)`. Si Garmin
  dit A et que vous dites B, vous gagnez et le coach le signale une fois. Un matériel Garmin sans
  puce n'est jamais attribué en silence ni crédité à la paire par défaut (`gear_source:
  garmin_unmapped`) ; une puce `- <nom Garmin> — garmin: <uuid> (ignorée)` fait taire propositions
  et alertes. La provenance est tracée dans `gear_source` (`garmin`/`chat`/`garmin_unmapped`) ; règle exécutée par `python3 scripts/arc_index.py gear-attribution`.
- **Synchronisation automatique.** `scripts/daily-sync.sh` passe `--disallowedTools` pour
  `add_gear_to_activity` et `remove_gear_from_activity`, ainsi que pour les outils d'écriture de
  séances et de parcours (`schedule_workouts`, `upload_workout`, `delete_workout`…) : le run non
  surveillé ne peut pas écrire chez Garmin. **Limite** : en mode passerelle l'appel passe par l'outil unique
  `mcp__leanproxy__invoke_tool`, qui ne peut pas être filtré par sous-outil — seule la consigne du skill
  protège alors ; préférez le mode direct pour un run non surveillé.
- **Retour vers Garmin (facultatif).** Une attribution faite en chat peut être poussée vers Garmin
  si vous le confirmez ; sans confirmation, rien n'est écrit.
- **Installations existantes.** Relancez `./install.sh` : la liste blanche de `.mcp.json` est
  mise à jour. En mode passerelle, éditez à la main `GARMIN_ENABLED_TOOLS` de
  `~/.config/leanproxy_servers.yaml` (voir l'avertissement plus haut) pour y ajouter
  `get_gear,get_activity_gear,add_gear_to_activity`. `/coach-doctor` (`gear_sync`) signale une liste
  blanche trop ancienne et les paires du profil sans `garmin:` — sans jamais contacter Garmin.
- **Source intervals.icu.** Voir [Configuration Intervals.icu](intervals-setup.md#materiel-et-attribution-par-seance).

## Authentification

Les tokens Garmin sont stockés dans `~/.garminconnect/` et sont valides environ **6 mois**.

### Vérifier les tokens

```bash
uv run garmin-mcp-auth --verify
```

### Renouveler l'authentification

```bash
uv run garmin-mcp-auth
```

## Données accessibles

Les agents accèdent aux outils Garmin directement (mode direct) ou via `leanproxy_invoke_tool(server="garmin", tool="...")` (mode passerelle) :

- **Activités** : liste, détails, fichiers FIT
- **Santé** : HRV, sommeil, stress, fréquence cardiaque au repos
- **Calendrier** : séances planifiées, push d'entraînements
- **Planification** : création de séances (course, fractionné, renforcement)

## Dépannage

| Problème | Solution |
|---|---|
| `garmin-mcp` introuvable | `uv tool install --python 3.12 git+https://github.com/Taxuspt/garmin_mcp@cfc5d799ab0f165e837f1188a1d093c65838aaf7` |
| Tokens expirés | `uv run garmin-mcp-auth` |
| `leanproxy-mcp` introuvable (mode passerelle) | `brew tap mmornati/leanproxy-mcp && brew install leanproxy-mcp` |
| Erreur de connexion | Vérifiez que `garmin-mcp` fonctionne : `garmin-mcp stdio` |

Voir aussi la page [Dépannage](troubleshooting.md).

!!! info "Pas de montre Garmin ?"
    `./install.sh --source intervals` remplace tout ce qui précède par
    Intervals.icu (COROS, Suunto, Polar, Apple...) — voir
    [Configuration Intervals.icu](intervals-setup.md).
