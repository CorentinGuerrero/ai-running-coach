# Montres COROS (audit du MCP officiel, #168)

Cette page trace l'audit du **MCP officiel de COROS** et la décision prise pour
le projet. Date de l'audit : 3 octobre 2026. Légende utilisée partout :
**vérifié** = constaté par nous (sonde HTTP sans authentification, ou lecture
d'une source publique citée) ; **non vérifié** = rapporté par un tiers ou
non confirmable sans compte COROS autorisé (nous n'avons jamais tenté de nous
authentifier).

## Décision

!!! success "Décision : pas de source `coros` — Intervals.icu reste le chemin supporté"
    Le MCP officiel est **ajoutable à la main pour un usage interactif**
    (voir ci-dessous), mais il est **hors des tables de correspondance**, jamais
    utilisé par la synchronisation sans tête (`/garmin-daily-sync`) et jamais
    installé par `install.sh`. Les athlètes COROS passent par
    [Intervals.icu](intervals-setup.md) (`./install.sh --source intervals`).

Pourquoi pas une source `coros` :

1. **Les noms d'outils ne sont pas vérifiables à la source.** `tools/list`
   exige un jeton OAuth ; le serveur n'est pas open source. Les seuls noms
   connus viennent d'un projet tiers (voir « Références »), qui annonce 22
   outils, alors qu'une revue de presse en compte 15 en 5 groupes : la liste
   évolue et nous ne pouvons pas l'épingler à un commit comme pour
   `garmin-mcp` ou `intervals-icu-mcp`. Règle du projet : jamais de nom d'outil
   deviné.
2. **L'exécution sans tête n'est pas démontrée.** L'authentification est
   OAuth 2.0 interactive (code d'autorisation + PKCE) ; selon le tiers, le
   jeton d'accès dure environ 30 jours et le jeton de rafraîchissement est
   **à usage unique** (rotation). Le support documenté par COROS ne cite pas
   Claude Code ni opencode (voir ci-dessous). Un cron qui rafraîchit seul un
   jeton à rotation, sans client MCP qui le persiste, n'est pas un socle
   acceptable pour `garmin-daily-sync`.
3. **Le gain est partiel.** Le MCP officiel apporterait des tours (laps)
   détaillés, le FIT et des mesures de récupération ; mais l'écriture de
   séances est contradictoire entre les sources (voir plus bas) et le FIT est
   plafonné à 50 fichiers par jour.

Ce qui ferait changer la décision : un `tools/list` public ou épinglé, un
support documenté de Claude Code (jeton persistant en mode sans tête), et une
écriture de séances confirmée. Le cas échéant, l'implémentation suivrait
exactement la méthode de #68 (table de correspondance, `install.sh --source`,
stubs, `coach-doctor`).

## Aujourd'hui : COROS via Intervals.icu

La montre synchronise ses activités et son bien-être vers Intervals.icu (via
l'intégration entre les deux comptes), puis `./install.sh --source intervals`
installe le serveur MCP épinglé `intervals-icu-mcp`. Limites déjà documentées :
pas de score de readiness (HRV + FC de repos uniquement), pas de FC de
récupération ni de `splits` par km, séances poussées en texte libre. Détail :
[Configuration Intervals.icu](intervals-setup.md#fonctionnalites-et-champs-indisponibles-avec-cette-source).
Le FIT d'une activité s'obtient par l'API REST d'Intervals.icu
([Fichiers FIT](intervals-setup.md#fichiers-fit)).

## Ce que propose le MCP officiel

### Faits vérifiés (sonde sans authentification, 3 octobre 2026)

| Fait | Preuve |
|---|---|
| Point d'accès `https://mcp.coros.com/mcp`, transport HTTP | `POST` sans jeton → `401` avec `www-authenticate: Bearer resource_metadata="https://mcpeu.coros.com/.well-known/oauth-protected-resource/mcp"` |
| Authentification **OAuth 2.0**, portées `openid mcp.tools offline_access` | document `/.well-known/oauth-protected-resource` (`bearer_methods_supported: header`) |
| Serveur d'autorisation `https://mcpeu.coros.com`, **PKCE S256**, **enregistrement dynamique de client** (`/connect/register`), flux `authorization_code`, `refresh_token`, `device_code` | document `/.well-known/oauth-authorization-server` |
| Instances régionales | en-tête `mr: mcp_eu_prod` ; `mcpcn` rapporté par un tiers, non sondé |

L'enregistrement dynamique et le flux appareil sont techniquement compatibles
avec un client MCP en ligne de commande, mais cela ne prouve pas que COROS
accepte un client arbitraire : **non vérifié**.

### Faits rapportés par COROS (page officielle, non vérifiés par nous)

Source : <https://coros.com/stories/coros-metrics/c/mcp-testing> (la page
d'aide <https://support.coros.com/hc/en-us/articles/5146420791060> renvoie 403
à un client automatisé).

- Clients cités : ChatGPT (mode développeur), Claude Desktop (connecteur
  personnalisé), Cursor, Gemini CLI. **Claude Code et opencode ne sont pas
  cités.**
- Lecture : activités et splits, métriques de forme (VO2max, puissance de
  course, allure seuil, prédictions), charge, récupération, santé quotidienne
  (pas, calories, sommeil, HRV, stress, FC de repos), profil et appareils,
  fichiers `.fit` (GPS, seconde par seconde), cycle menstruel.
- Écriture : création/édition de plans et de séances (course sur route, trail,
  vélo), plans de 4 à 16 semaines, planification jusqu'à 14 jours à l'avance.
  **Contradiction** : un compte rendu de mai 2026 décrit le lancement comme
  lecture seule (« écriture à venir ») et un projet tiers a constaté des
  erreurs `Unknown tool` sur les outils d'écriture. L'état actuel de
  l'écriture est donc **non vérifié**.
- Limites : 50 demandes de fichiers `.fit` par jour ; accès « uniquement après
  autorisation explicite » de l'utilisateur.
- Calendrier : URL unique consolidée le 19 mai 2026 selon COROS (et non en
  juillet 2026 comme supposé dans l'issue).

### Noms d'outils rapportés par un tiers (non vérifiés)

Relevés dans `ADAPTERS.md` de `xiaolouJB/ai-running-coach` au commit
`5f2c4a2018e52f9fdcabdc7adf15cb0ee7aa33fc`. Ce dépôt les dit obtenus par un
`tools/list` en direct, mais nous ne pouvons pas le confirmer : **tous « non
vérifiés »** pour ce projet, informatifs seulement.

| Besoin | Outil rapporté (non vérifié) | Note rapportée |
|---|---|---|
| Liste d'activités | `querySportRecords` | texte formaté, non JSON ; 404 intermittents rapportés |
| Détail d'une activité | `getActivityDetail` | charge, effets d'entraînement, effort perçu |
| Tours (laps) | `queryActivityLapData`, `queryCustomActivityLapData` | allure, FC, puissance, contact au sol, cadence |
| FIT | `queryActivityFitFileDownloadUrls`, `downloadActivityFitFiles` | 50 fichiers/jour |
| HRV | `querySleepHrv` | remplace un ancien outil supprimé |
| Sommeil | `querySleepData` | |
| FC de repos | `queryRestingHeartRate` | |
| Stress | `queryStressLevel`, `queryStressTimeSeries` | |
| Forme / prédictions | `queryFitnessAssessmentOverview` | |
| Charge | `queryTrainingLoadAssessment` | rapport de charge fourni |
| Récupération | `queryRecoveryStatus` | pourcentage et heures estimées |
| Planning existant | `queryTrainingSchedule` | |
| Profil / appareils | `queryUserInfo`, `queryDevices` | |
| Cycle | `queryMenstruationCycles` | |

Le projet communautaire non officiel
[`cygnusb/coros-mcp`](https://github.com/cygnusb/coros-mcp) (26 outils, login
e-mail/mot de passe, indépendant de COROS) n'a **pas** été retenu : il passe
par une API privée avec les identifiants du compte.

## Utilisation manuelle, en interactif (hors périmètre du projet)

Pour interroger vos données COROS dans une conversation, vous pouvez ajouter le
connecteur officiel vous-même, à vos risques, **en plus** de la source
configurée :

- Claude Desktop : Réglages → Connecteurs → connecteur personnalisé, URL
  `https://mcp.coros.com/mcp` (procédure indiquée par COROS).
- Claude Code (non documenté par COROS, **non testé ici**) : la commande
  générique `claude mcp add --transport http coros https://mcp.coros.com/mcp`
  puis `/mcp` pour l'autorisation OAuth.

Dans ce cas, le coach ne connaît pas ces outils : rien dans `AGENTS.md`, les
agents ou les skills ne les utilise, rien n'est persisté au contrat `arc`
automatiquement, et la synchronisation sans tête ne s'en sert jamais.

## Références

- Page COROS : <https://coros.com/stories/coros-metrics/c/mcp-testing>
- Revue de presse : <https://the5krunner.com/2026/05/13/coros-mcp-ai-data/>
- Projet tiers de référence : <https://github.com/xiaolouJB/ai-running-coach> (commit `5f2c4a2018e52f9fdcabdc7adf15cb0ee7aa33fc`, `ADAPTERS.md`)
- Projet non officiel : <https://github.com/cygnusb/coros-mcp>
- Sonde : `POST https://mcp.coros.com/mcp` (401) et les deux documents `/.well-known/` ci-dessus, le 3 octobre 2026
