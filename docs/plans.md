# Gabarits de périodisation (`arc_plan_templates.py`)

Jusqu'ici, le coach écrivait chaque bloc d'entraînement « à main levée » : la
périodisation et l'affûtage ne vivaient que dans son prompt. Les gabarits
rangent cette structure dans des **données** (`config/plans/*.json`, livrées
avec le moteur) et un script (`scripts/arc_plan_templates.py`) les **vérifie**
au lieu de se fier à de la prose.

!!! note "Un point de départ, jamais un plan imposé"
    Le profil de l'athlète, le bilan matinal et les [garde-fous](guardrails.md)
    priment toujours. Chaque semaine écrite à partir d'un gabarit repasse
    `arc_guardrails.py check` sur l'historique réel. Cette page décrit les
    gabarits et leur validation ; le squelette daté d'un bloc (date de course,
    disponibilité, historique) viendra avec
    [#190](https://github.com/mmornati/ai-running-coach/issues/190).

## Les gabarits livrés

| Identifiant | Sport | Objectif visé (distance) | Durée du bloc | Pic hebdomadaire indicatif |
|---|---|---|---|---|
| `trail_court` | trail | jusqu'à 30 km | 8 à 16 semaines (défaut 12) | 4–7 h |
| `marathon_trail` | trail | 30 à 60 km (~42 km, ~2 000 m D+) | 12 à 20 semaines (défaut 16) | 6–10 h |
| `ultra_80_100` | trail | 60 à 130 km (cœur de cible : 80–100 km) | 16 à 24 semaines (défaut 20) | 8–13 h |
| `cent_miles` | trail | 130 km et plus (~160 km) | 20 à 29 semaines (défaut 24) | 10–16 h |
| `route_semi` | route | 15 à 30 km | 8 à 16 semaines (défaut 12) | 3–6 h |
| `route_marathon` | route | 30 à 60 km (~42 km) | 12 à 20 semaines (défaut 16) | 4–9 h |

Les bandes de distance ne se chevauchent pas pour un même sport (vérifié) : la
distance de l'objectif actif désigne au plus un gabarit. Une course de 50 km
tombe dans le gabarit « marathon trail », la plus proche : à adapter, et le
coach le dit. Les gabarits route sont utilisables quand `[sport].primary =
road` ; ils n'ont pas de D+.

## Ce que contient un gabarit

Cinq phases, dans cet ordre : **base**, **développement**, **spécifique**,
**affûtage** (la semaine de course en est la dernière semaine), puis
**récupération**, qui suit la course et ne compte pas dans la durée du bloc.
Pour chacune :

- une **durée en semaines** (minimum–maximum) ;
- la progression du **volume** et du **D+** (trail), en pourcentage de la
  semaine pic (= 100) : une valeur de début et de fin de phase ;
- la **répartition d'intensité** facile / modérée / difficile, au moins ~75 %
  de facile (approche polarisée « 80/20 ») ;
- le **nombre maximal de séances de qualité** par semaine ;
- la part de la **sortie longue** dans le volume hebdomadaire et son plafond en
  minutes ;
- l'**accent de renforcement** (un nom seulement : force maximale, force
  d'endurance, pliométrie/excentrique, entretien, mobilité — la bibliothèque
  d'exercices est une autre étape de l'épopée) ;

et, pour le gabarit entier, une **semaine allégée** toutes les N semaines
(facteur de volume et de D+, une seule séance de qualité au plus).

Voir ce qu'un gabarit donne, semaine par semaine :

```bash
python3 scripts/arc_index.py plan-templates                       # liste
python3 scripts/arc_index.py plan-templates --distance-km 90      # choisi d'après l'objectif
python3 scripts/arc_index.py plan-templates --format marathon_trail --weeks 14
python3 scripts/arc_index.py plan-templates --format route_semi --json
```

La sortie par défaut est un tableau lisible ; `--json` rend la même chose pour
les agents (gabarit, répartition des semaines par phase, semaines résolues,
problèmes de validation, seuils utilisés, hypothèses). Lecture seule : aucun
index ni fichier n'est créé.

## Étirer ou comprimer : règles déterministes

Pour un nombre de semaines donné, entre le minimum et le maximum du gabarit :

1. chaque phase démarre à son minimum ;
2. les semaines restantes sont distribuées **une par une**, en parcourant
   l'ordre d'étirement du gabarit (développement, spécifique, base, affûtage)
   en boucle, à chaque phase qui n'a pas atteint son maximum ;
3. dans une phase, le volume (et le D+) progresse **linéairement** du début à la
   fin ;
4. la semaine *w* est une **semaine allégée** si *w* est un multiple de N, si
   sa phase est base, développement ou spécifique, et si la semaine suivante
   n'est pas déjà l'affûtage (la semaine avant l'affûtage reste la semaine pic) ;
   son volume vaut le facteur du gabarit × la dernière semaine non allégée.

Mêmes entrées, mêmes sorties : aucun aléa. Hors des bornes du gabarit, la
commande refuse (« 99 semaines hors de 20–29 »).

## La validation, cœur du livrable

`validate_template` (et la commande `plan-templates`, qui affiche son verdict)
vérifie chaque gabarit, pas seulement sa forme :

- **schéma** : clés inconnues refusées, pourcentages dans leurs bornes,
  répartition d'intensité qui totalise 100, phases dans l'ordre, accent de
  renforcement connu, mention « approximation du projet » présente ;
- **durées** : la somme des minima de phases tient dans le minimum du bloc, la
  somme des maxima couvre son maximum — toute longueur du bloc est réalisable ;
- **garde-fous**, sur les semaines **résolues pour chaque longueur possible** du
  bloc, avec les seuils du workspace (`[guardrails]`) :
    - [R2](guardrails.md) : hausse du volume ≤ le seuil (10 % par défaut) face à
      la moyenne des 4 semaines précédentes (référence `mean4`, défaut du
      moteur) **et** face à la dernière semaine non allégée ;
    - R3 : la même chose pour le D+ ;
    - R6 : part de la sortie longue ≤ le seuil (35 % par défaut) ;
    - R7 : pas plus de 3 séances de qualité par semaine (le gabarit ne place pas
      de jours : les espacer est l'affaire du squelette) ;
- **structure** : semaines allégées présentes dès que le bloc compte au moins
  deux cycles ; affûtage placé dans les dernières semaines, décroissant, sous le
  pic, avec au moins 25 % de réduction au final ; semaine pic à 100 %.
- **cohérence entre gabarits** : identifiants uniques, bandes de distance sans
  chevauchement.

!!! warning "Ce que la validation implique : démarrer proche du pic"
    Avec le seuil R2 par défaut (+10 % face à la moyenne de 4 semaines, creusée
    par les semaines allégées), une montée de charge raide fait déclencher le
    garde-fou. Les gabarits livrés démarrent donc à environ 80–90 % de la
    semaine pic (plus bas pour les blocs longs) et progressent de quelques
    pourcents par semaine : **ils décrivent la forme d'un bloc à partir du
    volume que l'athlète tient déjà**, pas une reprise depuis zéro. Si
    l'athlète est loin du pic visé, le coach baisse le pic ou prévoit un bloc
    de mise en route au lieu d'étirer le gabarit.

La validation porte sur les seuils, pas sur l'athlète : elle ne dit rien de
l'historique réel, que seul `arc_guardrails.py check` évalue.

## D'où viennent les chiffres

Tous les nombres (durées de phase, pourcentages du pic, D+, répartition
d'intensité, plafonds de sortie longue, fréquence des semaines allégées,
affûtage, pics horaires) sont des **approximations du projet** : des points de
départ prudents, réglables en éditant les fichiers `config/plans/*.json` (la
validation dit aussitôt si le résultat reste cohérent avec les garde-fous).
Ils ne proviennent d'aucun protocole publié et aucun plan commercial n'est
reproduit.

Deux publications, vérifiées dans Crossref, orientent seulement la *direction*
de deux choix, jamais un chiffre :

- Mujika I., Padilla S., « Scientific bases for precompetition tapering
  strategies », *Medicine & Science in Sports & Exercise* 35(7):1182-1187, 2003,
  [doi:10.1249/01.MSS.0000074448.73931.11](https://doi.org/10.1249/01.MSS.0000074448.73931.11)
  — l'affûtage réduit le volume en conservant l'intensité ;
- Seiler S., « What is best practice for training intensity and duration
  distribution in endurance athletes? », *International Journal of Sports
  Physiology and Performance* 5(3):276-291, 2010,
  [doi:10.1123/ijspp.5.3.276](https://doi.org/10.1123/ijspp.5.3.276) — la
  distribution d'intensité polarisée.

## Dans le workflow du coach

Pour un nouveau bloc, le coach cherche le gabarit de l'objectif actif
(distance et sport), lit sa résolution semaine par semaine, l'adapte au profil,
au bilan matinal et à l'historique, puis habille lui-même les séances. Sans
gabarit adapté, il construit le bloc comme avant et le dit. Les pourcentages
sont relatifs à une semaine pic que le coach dérive de l'historique réel — il
n'invente jamais de volumes absolus. Voir [Coach](agents/coach.md#gabarits-de-periodisation-189).
