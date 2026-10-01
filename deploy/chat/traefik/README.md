# Chat avec le coach derrière Traefik

Le chat est un service (`scripts/arc_chat.py`, installé par `./install.sh --chat`) qui
tourne sur la **machine coach**. Le tableau de bord, lui, est servi par son conteneur
(`deploy/dashboard/`). Les deux se partagent **le même nom d'hôte** : Traefik envoie
`/api/chat/*` à la machine coach et tout le reste au conteneur. Le navigateur n'a donc
qu'une origine (pas de CORS, cookie de session SSO unique).

`dynamic.yml` est un exemple pour le **fournisseur `file`** de Traefik v3, quand le chat
tourne sur l'hôte. Chat en conteneur : les mêmes routeurs sont déclarés par labels dans
`deploy/dashboard/compose.chat.yaml` (voir `docs/dashboard/chat.md`).

## Les deux routeurs

| Routeur | Règle | SSO | Pourquoi |
|---|---|---|---|
| `arc-chat` | `Host(...) && PathPrefix(/api/chat)` | **oui, obligatoire** | Tout le chat : sessions, messages, approbations depuis la page. |
| `arc-chat-approve` | `Host(...) && PathRegexp(^/api/chat/approve/<id>.<secret>/(allow\|deny)$) && Method(POST)` | non, limité en débit | Les boutons « Appliquer / Refuser » des notifications ntfy. |

Priorités explicites (300 et 200) : elles passent devant le routeur du tableau de bord,
dont la règle `Host(...)` seule est plus courte.

### Pourquoi le second routeur n'a pas de SSO

Une notification ntfy s'ouvre sur le téléphone : le bouton envoie une requête HTTP
directe, **sans le cookie de session SSO** (et sans navigateur pour se connecter).
L'autorisation vient du **jeton** contenu dans l'URL :

- signé, à usage unique — les deux jetons (autoriser/refuser) sont brûlés dès le
  premier usage ;
- lié à une proposition précise et à son contenu (un jeton ne peut pas appliquer autre
  chose) ;
- de courte durée (`[chat].ntfy_token_ttl_s`, 30 min par défaut) ;
- seul le hash sha256 est stocké côté service ;
- exigé avec l'en-tête `X-ARC-Chat: 1` (posé par le bouton ntfy).

**Le jeton voyage dans la notification** : quiconque peut lire le sujet ntfy peut appuyer
sur le bouton. Le service n'envoie donc les boutons « Appliquer / Refuser » que si
`[notifications].ntfy_token_file` est renseigné (sujet à accès contrôlé, jeton d'accès
ntfy). Sans lui, seul le bouton « Ouvrir » (page derrière le SSO) est envoyé et un
avertissement est journalisé une fois. Réservez donc ce routeur aux sujets protégés.

Le jeton a la forme `<id>.<secret>` (deux segments `[A-Za-z0-9_-]` séparés par un point) :
le motif du routeur l'exige, un point dans le jeton est donc indispensable.

Le routeur est donc limité à **POST** et à ce motif exact, et un middleware `rateLimit`
freine toute tentative de devinette. Tout le reste de `/api/chat` reste derrière le SSO.
Si vous préférez ne jamais ouvrir cette porte, désactivez les boutons
(`[chat].ntfy_quick_approve = false`) et supprimez le routeur : il reste le bouton
« Ouvrir », qui passe par la page et donc par le SSO.

## Réglages du service sur la machine coach

À mettre dans `config/workspace.user.toml` (section `[chat]`) :

```toml
[chat]
enabled = true
auth = "proxy"                       # l'identité vient du SSO, pas de la boucle locale
listen = "192.168.1.20"              # l'IP LAN/Tailscale de la machine coach (jamais 0.0.0.0 si évitable)
port = 8766
trusted_proxies = ["192.168.1.10"]   # l'IP SOURCE de Traefik (ou son nom d'hôte) — le service refuse toute autre
public_url = "https://coach.example.com"   # requis pour les boutons ntfy
auth_header = "X-authentik-username"       # Authelia : "Remote-User"
allowed_users = ["moi"]                    # vide = tout utilisateur authentifié
```

- **`auth = "proxy"`** : le service exige l'en-tête d'identité sur chaque requête (sauf
  `/approve/<jeton>` et `/healthz` depuis la boucle locale) et n'accepte que les
  connexions venant de `trusted_proxies`. Traefik reste la vraie barrière ; c'est une
  défense en profondeur.
- **`listen`** : n'écoutez que sur l'interface que Traefik atteint. Sur la même machine
  que Traefik, gardez `127.0.0.1` et `auth = "proxy"` avec `trusted_proxies =
  ["127.0.0.1"]`.
- **`public_url`** : l'URL publique du tableau de bord ; elle sert à construire les liens
  des notifications.
- **`auth_header`** : le nom de l'en-tête que votre SSO pose après vérification. Chez
  Authentik : `X-authentik-username` (listez-le dans `authResponseHeaders` du
  `forwardAuth`). Chez Authelia : `Remote-User`. Le `forwardAuth` **écrase** l'en-tête
  envoyé par le client, ce qui empêche l'usurpation.
- **`allowed_hosts`** : laissé vide, il est déduit de `public_url` (plus la boucle
  locale).

Ne publiez **aucun port** de la machine coach sur Internet : seul Traefik doit pouvoir
joindre `listen:port` (pare-feu, ou réseau LAN/Tailscale).

## Vérifier

```bash
scripts/coach-chat.sh status                          # service + healthz local
curl -i https://coach.example.com/api/chat/status     # sans session : redirigé vers le SSO
python3 scripts/coach_doctor.py --check chat_service
```

Après le SSO, `GET /api/chat/status` répond en JSON. Une requête `POST` vers
`/api/chat/approve/x.y/allow` sans en-tête `X-ARC-Chat` ou avec un jeton inconnu est refusée
par le service, pas par Traefik.
