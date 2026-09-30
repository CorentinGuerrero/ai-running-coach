# Le chat avec le coach

La page **Coach** du tableau de bord : vous écrivez au coach depuis le navigateur — ordinateur
ou téléphone —, avec la même connexion que le reste du tableau de bord. Derrière, ce sont les
mêmes agents, les mêmes skills, le même serveur MCP Garmin et les mêmes fichiers Markdown
qu'en session dans votre IDE : le chat n'invente aucune source de vérité.

- chaque étape (fichier lu, outil appelé) apparaît dans une trace repliable, avec ce que le
  coach en dit en travaillant — seule la réponse finale reste affichée ;
- les réponses arrivent au fil de l'eau ; si le fournisseur est saturé, une ligne l'indique
  pendant les nouvelles tentatives au lieu d'une page muette ;
- les blocs de données (` ```arc `, JSON) sont repliés, les tableaux mis en forme ;
- **toute écriture vers Garmin ou Intervals.icu attend votre accord** : une carte montre
  l'avant/après, vous appliquez ou refusez — depuis la page ou depuis la notification ;
- un compteur affiche le coût de la conversation et le budget du jour.

!!! warning "Une clé API, pas votre abonnement"
    Un front maison **ne peut pas** utiliser un abonnement Claude Pro/Max ou ChatGPT
    (voir [Le coach dans la poche](../mobile.md#ce-qui-nest-pas-possible-et-pourquoi)). Le chat
    appelle le modèle avec une **clé API facturée au token** — Anthropic, OpenRouter ou toute
    API compatible OpenAI. Un plafond quotidien l'encadre. Pour parler au coach sans clé API,
    gardez [Remote Control](../mobile.md#5-le-coach-sur-le-telephone-remote-control).

```mermaid
flowchart LR
    N[📱 navigateur] -->|HTTPS| P[Traefik + SSO]
    P -->|/| D[tableau de bord<br/>lecture seule]
    P -->|/api/chat| C[service de chat<br/>machine coach]
    C --> B{backend}
    B -->|claude| S[Claude Agent SDK]
    B -->|opencode| O[serveur OpenCode<br/>OpenRouter, DeepSeek…]
    C --> W[(workspace)]
    C --> G[garmin-mcp]
    C -.->|approbation| T[ntfy → téléphone]
```

Le tableau de bord reste **en lecture seule** et ne voit jamais la clé API : c'est un service
à part (`scripts/arc_chat.py`), sur la machine coach, qui écrit dans le workspace.

## Choisir un fournisseur

| | Claude (API Anthropic) | OpenRouter (ou API compatible OpenAI) |
|---|---|---|
| Harnais | Claude Agent SDK — le moteur de Claude Code | serveur OpenCode |
| Modèle par défaut | `claude-sonnet-5-5` | `openrouter/deepseek/deepseek-v4-pro` |
| Fidélité aux agents/skills | identique à Claude Code | bonne ; dépend du modèle |
| Prérequis | `pip install claude-agent-sdk` (Python ≥ 3.10) | binaire `opencode` |
| Coût indicatif | quelques centimes par échange | moins, selon le modèle |

Pourquoi Sonnet et pas Haiku pour le chat : c'est là que se prennent les décisions délicates
(garde-fous médicaux, modification du plan, écriture Garmin). Haiku coûte la moitié ; une
mauvaise décision coûte plus. Haiku 4.5 reste le défaut de la
[synchronisation automatique](../mobile.md#modeles-par-defaut), tâche répétitive et très cadrée.

!!! note "Modèles bon marché"
    Un modèle peu fiable en appel d'outils peut casser le contrat ```` ```arc ````, sauter le
    bilan matinal ou adoucir un garde-fou. Validez un modèle sur quelques échanges réels avant
    de lui confier votre plan, et gardez un œil sur la trace des étapes.

## Installer

Sur la machine coach :

```bash
./install.sh --llm anthropic --chat
```

ou, pour OpenRouter :

```bash
./install.sh --llm openrouter --chat
```

`--llm` règle **à la fois** le chat (`[chat]`) et la synchronisation automatique (`[sync]`) :
un seul fournisseur pour tout. Si un exécuteur était déjà configuré autrement, il est remplacé
**avec un avertissement** qui indique l'ancienne valeur et comment revenir en arrière. Les deux
sections restent indépendantes : vous pouvez ensuite remettre la synchronisation sur
l'abonnement (`[sync].runner = "claude"`) et garder le chat sur l'API.

Options utiles :

| Option | Effet |
|---|---|
| `--model ID` | autre modèle (ex. `--model anthropic/claude-sonnet-5.5` sur OpenRouter) |
| `--base-url URL` | avec `--llm openai` : Mistral, Ollama, vLLM… |
| `--chat-budget EUR` | plafond quotidien du chat (défaut 2 €) |
| `--sync-budget EUR` | plafond quotidien de la synchronisation (défaut 0,50 €) |

Puis la clé, dans `~/.config/ai-running-coach/llm.env` (créé en mode 600, jamais versionné) :

```bash
ANTHROPIC_API_KEY=sk-ant-...        # ou OPENROUTER_API_KEY=sk-or-...
```

!!! danger "N'exportez pas `ANTHROPIC_API_KEY` dans votre shell"
    Cette variable fait basculer Claude Code sur la clé API et **casse Remote Control**, qui
    exige l'abonnement. Le fichier `llm.env` n'est lu que par le service de chat et la
    synchronisation.

Le service tourne en tâche de fond (systemd `--user` sur Linux, LaunchAgent sur macOS) :

```bash
scripts/coach-chat.sh status
```

Journal : `logs/chat.log` dans le workspace. Diagnostic :

```bash
python3 scripts/coach_doctor.py --check chat_service
```

## En local

Sans reverse proxy, ouvrez le tableau de bord (`scripts/dashboard.sh`) : l'entrée **Coach**
apparaît dans la navigation dès que `[chat].enabled = true`. Le tableau de bord, qui écoute sur
`127.0.0.1`, relaie `/api/chat/*` vers le service de chat (port `[chat].port`, 8766). Rien
n'écoute hors de la machine.

## Derrière Traefik et un SSO

La page est servie par le même hôte que le tableau de bord ; Traefik envoie `/api/chat/*` au
service de chat, **avec le même middleware d'authentification**. Exemple complet de
configuration dynamique : `deploy/chat/traefik/dynamic.yml` et son `README.md`.

Côté machine coach, dans `config/workspace.user.toml` :

```toml
[chat]
auth = "proxy"
listen = "192.168.1.20"              # interface joignable par Traefik
trusted_proxies = ["192.168.1.10"]   # l'adresse de Traefik, et elle seule
auth_header = "X-authentik-username" # Authelia : "Remote-User"
public_url = "https://coach.example.org"
allowed_users = ["vous"]             # optionnel
```

Ce que le service vérifie à chaque requête, en plus du SSO :

- l'adresse de l'appelant est celle de Traefik (`trusted_proxies`) ;
- l'en-tête d'identité posé par le SSO est présent (et autorisé, si `allowed_users`) ;
- le nom d'hôte est attendu (`allowed_hosts`, à défaut celui de `public_url`) ;
- toute requête qui modifie quelque chose porte l'en-tête `X-ARC-Chat` et vient de la même
  origine : un autre site ne peut pas agir à votre place avec votre cookie de session ;
- un nombre de tours limité par minute (`rate_limit_per_min`) et le budget du jour.

## Approuver depuis le téléphone

Quand une carte d'approbation reste sans réponse (`ntfy_delay_s`, 60 s par défaut — ou tout de
suite si aucune page n'est ouverte), une notification part sur votre téléphone via
[ntfy](../mobile.md#3-notifications-push-ntfy). Elle ne contient que le résumé du changement
(« Jeudi : fractionné → EF 45 min »), jamais vos données de santé.

- **Ouvrir** ouvre la carte dans le navigateur, derrière votre connexion habituelle.
- **Appliquer / Refuser** (si `ntfy_quick_approve = true`, défaut) agit directement depuis la
  notification. L'appli ntfy ne porte pas votre cookie de session : ces deux boutons passent
  par une route dédiée, **sans SSO**, protégée autrement — lien à usage unique, valable
  30 minutes (`ntfy_token_ttl_s`), lié à ce changement précis (un lien ne peut rien approuver
  d'autre), débit limité par adresse. Mettez `ntfy_quick_approve = false` pour ne garder que « Ouvrir ».

!!! warning "Les boutons rapides exigent un sujet ntfy protégé"
    Le lien à usage unique est **dans la notification** : quiconque est abonné au sujet peut
    l'utiliser. Le service n'envoie donc « Appliquer / Refuser » que si
    `[notifications].ntfy_token_file` est renseigné (sujet à accès contrôlé, jeton d'accès ntfy).
    Sans ce fichier, seul « Ouvrir » part et un avertissement est journalisé une fois.
    Voir [Notifications](../mobile.md#3-notifications-push-ntfy).

    **Un `ntfy_token_file` renseigné ne suffit pas** : le service ne peut pas vérifier que le
    sujet est réellement protégé en lecture. Le sujet doit avoir des ACL de lecture — côté
    serveur ntfy, `auth-default-access: deny-all` et un utilisateur disposant des droits de
    lecture/écriture sur ce sujet (celui du jeton). Sinon, tout abonné anonyme du sujet reçoit
    les liens : mettez alors `ntfy_quick_approve = false`.

`public_url` doit être renseigné pour que les boutons pointent au bon endroit.

Le coach attend votre réponse une dizaine de minutes (`approval_wait_s`). Passé ce délai, la
proposition reste **en attente** (`approval_ttl_s`, 24 h) : si vous l'appliquez plus tard, la
conversation reprend et le coach exécute exactement ce qui a été approuvé — rien d'autre. Si
la session est occupée à ce moment-là, la reprise attend la fin du tour en cours (et repart au
redémarrage du service si celui-ci s'arrête entre-temps). Si elle est impossible (budget du jour
atteint, erreur du fournisseur, le modèle n'a pas refait l'appel), la carte passe à « Approuvée
mais non exécutée », une erreur est écrite dans la conversation et une notification vous le dit.
Interrompre un tour pendant qu'une carte attend la marque « Annulée (tour interrompu) » — pas
« refusée ».

## Ce que le coach peut faire

La politique est dans `config/chat-policy.toml` (versionné) et s'applique quel que soit le
fournisseur :

| Action | Règle |
|---|---|
| Lire le workspace, lire Garmin / Intervals.icu | autorisé (jamais les fichiers de secrets) |
| Écrire dans `activities/ medical/ nutrition/ planning/ rapports/ gear/` | autorisé |
| Écrire vers Garmin / Intervals.icu (planifier, supprimer, téléverser…) | **votre accord à chaque fois** |
| Scripts du projet (`arc_index.py`, `arc_log.py`…) | autorisé, liste fermée **et options fermées** : chaque script n'accepte que ses options déclarées dans `config/chat-policy.toml`, et tout chemin doit rester dans le workspace (jamais absolu, `~`, `..`, secret ni `.arc/`) ; les sorties ne s'écrivent que sous `activities/ medical/ nutrition/ planning/ rapports/ gear/` |
| Shell libre, autre dossier, autre site | refusé |
| Météo (`wttr.in`), points d'eau (OpenStreetMap) | autorisé |

Les conversations sont gardées dans `.arc/chat/` (jetable, hors versionnement). Ce que le coach
décide est écrit comme d'habitude dans les fichiers Markdown, avec leur bloc ```` ```arc ````.

## Budget

`[chat].daily_budget_eur` (2 € par défaut) plafonne la dépense du jour ; une fois atteint, le
chat le dit et n'appelle plus le modèle jusqu'au lendemain. Modifiez-le dans
`config/workspace.user.toml` ou avec `./install.sh --chat-budget 5`. Les fournisseurs facturent
en dollars : `usd_eur_rate` (0,92) sert à la conversion.

Chaque tour **réserve** au plus `turn_budget_max_eur` (1 € par défaut) sur le budget restant du
jour : un échange qui s'emballe s'arrête là, et le reste demeure disponible pour une autre
conversation ou une approbation tardive. Avec `0`, un tour réserve tout le reste du jour et une
seconde conversation simultanée est refusée (« budget réservé par une autre conversation »).

!!! note "Coût inconnu"
    Avec OpenCode, un modèle absent de son catalogue de prix remonte un coût nul : le plafond ne
    peut alors rien compter. Surveillez la dépense côté fournisseur (OpenRouter affiche la
    consommation par clé) et fixez-y aussi une limite.

## Vos données de santé

Le chat envoie au fournisseur de modèle vos données d'entraînement et de santé (HRV, sommeil,
blessures). Choisissez-le en conséquence : chez OpenRouter, limitez le routage aux fournisseurs
qui ne conservent pas les données et ne s'en servent pas pour l'entraînement (réglages de
confidentialité du compte). Voir aussi
[Le coach dans la poche](../mobile.md#vos-donnees-de-sante-et-le-fournisseur).

## Réglages

Toutes les clés : [Configuration — `[chat]`](../configuration.md#le-chat-avec-le-coach-chat).
Variables d'environnement utiles au dépannage : `ARC_LLM_ENV` (autre chemin que `llm.env`),
`ARC_CHAT_PING_S` (intervalle des pings du flux, 15 s), `ARC_OPENCODE_TRACE` (évènements bruts
d'OpenCode recopiés dans un fichier — échanges compris, à supprimer après le diagnostic).

## Dépannage

| Symptôme | Cause probable |
|---|---|
| « Service de chat injoignable » | service arrêté : `scripts/coach-chat.sh start`, puis `logs/chat.log` |
| « Authentification requise » | en-tête d'identité absent : vérifier `auth_header` et le middleware Traefik |
| « Hôte non autorisé » | `allowed_hosts` / `public_url` ne correspondent pas à l'adresse utilisée |
| Pas de notification d'approbation | `[notifications]` non configuré, ou `public_url` vide (pas de boutons) |
| « paquet claude-agent-sdk absent » | `pip install claude-agent-sdk` dans le Python du service |
| Budget atteint dès le matin | augmenter `daily_budget_eur`, ou passer à un modèle moins cher |
