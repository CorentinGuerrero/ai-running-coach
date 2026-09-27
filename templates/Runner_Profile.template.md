# Profil de l'athlète

> Modèle installé par `/coach-setup`. Ce fichier vit dans votre workspace et
> n'est **jamais** versionné dans le dépôt public. Complétez ce que vous voulez :
> chaque champ laissé vide sera simplement ignoré par les agents.
>
> Les agents lisent ce fichier avant toute planification. L'objectif en cours,
> lui, reste dans `planning/active_objective.md`.

## Identité & contexte

- **Prénom / surnom** :
- **Année de naissance** :
- **Années de pratique** :
- **Disponibilité hebdomadaire** : <!-- ex. 4 séances, 6 h au total -->
- **Jours impossibles** : <!-- ex. mardi, dimanche matin -->
- **Contraintes de vie** : <!-- travail, famille, déplacements réguliers -->

## Physiologie

- **FC max** :
- **FC de repos de référence** : <!-- votre ligne de base, pas la valeur du jour -->
- **FC au seuil** : <!-- FC tenue ~1 h à fond (seuil lactique), ex. 172 -->
- **Sexe** : <!-- facultatif : F ou H, sert uniquement au calcul de charge (TRIMP) -->
- **Zones / seuils** :
- **Allures de référence** : <!-- 5 km, 10 km, semi, marathon -->
- **Poids de forme** :
- **Besoin de sommeil** : <!-- ex. 7h30 ; 7 h 30 par défaut si vide (dette de sommeil 7 j) -->

## Historique & blessures

- **Meilleures performances** :
- **Antécédents de blessure** :
- **Zones fragiles à surveiller** :
- **Arrêts récents** : <!-- maladie, coupure, reprise -->

## Indices de performance (ITRA / UTMB)

> Facultatif. Ces indices ne sont **jamais** récupérés automatiquement par un
> agent ou un script : seul vous pouvez les écrire ici, ou demander
> explicitement à l'agent `coach` de les chercher sur le web pour vous — il
> vous montrera alors la valeur trouvée et sa source, et vous demandera
> confirmation avant de l'écrire. Nomenclature UTMB (`20k`/`50k`/`100k`/`100m`)
> vérifiée ; celle de l'ITRA par catégorie n'a pas pu être vérifiée à
> l'écriture de ce modèle — la catégorie reste donc du texte libre.
>
> Une seule source de vérité : l'**historique** ci-dessous. La valeur
> « actuelle » d'un indice est simplement sa ligne la plus récente — inutile de
> la dupliquer ailleurs dans ce fichier.

### Historique des indices

<!--
  Une puce de PREMIER NIVEAU par relevé daté, au format :
    - AAAA-MM-JJ — itra [catégorie] : <valeur>
    - AAAA-MM-JJ — utmb [20k|50k|100k|100m] : <valeur>

  La catégorie est facultative (indice général si omise). Pour l'UTMB, seules
  les quatre catégories ci-dessus sont reconnues ; toute autre valeur, comme
  une ligne qui ne respecte pas ce format, est ignorée (avec un avertissement
  au tableau de bord/CLI) plutôt que de fausser silencieusement le calcul.

  Exemples (à adapter, effacer les lignes que vous ne remplissez pas) :
  - 2025-11-01 — itra : 610
  - 2025-11-01 — itra L : 600
  - 2026-02-15 — utmb 100k : 560
-->


## Matériel & lieux

- **Lieu par défaut** : <!-- ville utilisée pour la météo, ex. « Tournai » -->
- **Créneau habituel** : <!-- ex. pause de midi (12 h-14 h), tôt le matin, soir -->
- **Terrain accessible** : <!-- forêt, piste, dénivelé, salle -->
- **Équipement** : <!-- salle de sport, home trainer, haltères, tapis -->
- **Sports croisés pratiqués** : <!-- vélo, natation, renforcement -->

### Chaussures

<!--
  Une puce de PREMIER NIVEAU par paire (pas de puce indentée dessous, elle
  serait ignorée comme chaussure et repliée dans la ligne du dessus), tout est
  facultatif sauf le nom. Segments séparés par un tiret cadratin " — " (le plus
  lisible), ou par un simple tiret ENTOURÉ D'ESPACES " - " (jamais un tiret
  sans espaces, qui peut faire partie du nom, ex. « Ultra-Trail ») :
    - <nom> — depuis <AAAA-MM-JJ> — alerte <N> km — id: <identifiant> (par défaut)

  - "depuis" : date d'achat — AAAA-MM-JJ, ou juste "mars 2026"/"03/2026" (1er du
    mois). Depuis #40, filtre l'attribution automatique des séances SANS
    matériel précisé à la chaussure "(par défaut)" (une séance datée avant
    n'y est pas rattachée) — sans effet sur une séance qui cite cet id.
  - "alerte" : seuil d'usure propre à cette paire, en km (ou "N miles"/"N mi",
    converti), sinon 700 km par défaut.
  - "id:" : identifiant explicite (sinon dérivé automatiquement du nom).
    OBLIGATOIRE si vous rachetez le même modèle (deux puces au même nom sans
    id explicite se voient sinon attribuer un identifiant renommé -2, -3… et
    un avertissement au tableau de bord).
  - "(par défaut)" : chaussure attribuée aux séances sans matériel précisé.
  - "(retirée)" : sortie de rotation — kilométrage conservé, jamais d'alerte.

  Exemple (à adapter, effacer les lignes que vous ne remplissez pas) :
  - Hoka Speedgoat 5 (bleues) — depuis 2026-03-01 — alerte 700 km — id: speedgoat-bleues (par défaut)
  - Hoka Speedgoat 5 (grises) — depuis 2026-09-01 — id: speedgoat-grises
  - Nike Pegasus (retirée)
-->


## Préférences de coaching

> Ce que la configuration (`config/workspace.user.toml` → `[coaching]`) ne peut
> pas exprimer. Écrivez librement.

- **Ce qui me motive** :
- **Ce qui ne marche pas avec moi** :
- **Sujets à ne pas commenter spontanément** : <!-- ex. le poids -->
- **Tolérance au risque** : <!-- prudent | équilibré | agressif, et pourquoi -->
- **Quand me poser une question plutôt que supposer** :

## Objectif actif

Voir `planning/active_objective.md` — source de vérité de l'objectif en cours.
