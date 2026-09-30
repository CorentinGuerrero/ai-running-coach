---
name: gear-inspection
description: Inspection photo d'une paire de chaussures — protocole de prise de vue (semelles, profil, arrière, tige, échelle), grille de lecture de l'état 🟢🟡🟠🔴, comparaison avec l'inspection précédente de la même paire, indices de foulée tirés de la zone d'usure (toujours un indice, jamais un diagnostic), relais vers l'agent medical seulement s'il est activé. Persiste gear/AAAA-MM-JJ_<gear_id>_inspection.md (bloc arc gear_inspection) et produit le bilan de carrière d'une paire retirée. Charger quand le coach propose une inspection (environ tous les 200 km, à l'alerte de seuil), quand l'athlète envoie des photos de ses chaussures ou décrit leur usure, ou quand une paire passe en retirée.
---

# Inspection photo des chaussures (#135)

Le compteur de kilomètres dit combien une paire a couru, pas dans quel état elle est.
Une photo des semelles, lue avec l'historique de l'athlète, donne une deuxième
opinion — et l'usure raconte un peu la foulée. **L'usure est un signal faible** : les
chaussures modernes (pile haute, rocker, mousses) la déforment (approximation du projet, pas une mesure publiée), et un motif d'usure
n'est **jamais un diagnostic**, seulement un indice à croiser.

## 1. Quand proposer une inspection

Une inspection est **proposée, jamais imposée** — l'athlète peut refuser sans motif.

- **~Tous les 200 km** depuis la dernière inspection de la paire, ou depuis son entrée
  en service quand elle n'en a jamais eu (approximation du projet, pas une norme).
- **À l'alerte de seuil** (paire ayant franchi son `alerte NNN km`, voir `arc_index.py gear`).
- **Sur demande** de l'athlète, ou quand il décrit une usure inhabituelle.

Le rappel se calcule, il ne se devine pas :

```bash
python3 scripts/arc_index.py inspections            # toutes les paires
python3 scripts/arc_index.py inspections --gear ID  # une paire
```

Par paire : `due` (`true` = inspection conseillée, `null` = indéterminé, la dernière
inspection n'ayant pas de `distance_m`), `due_reason` (`never_inspected`, `interval`,
`threshold_alert`, `baseline_unknown`), `km_since_inspection_m`, `condition_change`
(`worse`/`same`/`better` entre les deux dernières inspections) et l'historique
(`inspections`, plus récente d'abord). Le tableau de bord affiche le même rappel.

Ne **jamais** proposer une inspection en mode headless (`/garmin-daily-sync`) : c'est
une conversation, avec des photos. Une proposition par conversation suffit.

## 2. Protocole photo

Demander, dans cet ordre, en une seule liste courte :

1. **Les deux semelles à plat** (dessous), côte à côte, lumière rasante ou de face.
2. **Vue latérale à hauteur de semelle**, de chaque chaussure — plis de la mousse
   intermédiaire, compression.
3. **Vue arrière sur une surface plane** — inclinaison du talon, contrefort affaissé.
4. **La tige** (dessus) — déchirures, trous, usure du bout.
5. **Une pièce ou une règle dans le cadre** — indispensable pour toute mesure (§7).

Une photo floue, coupée ou trop sombre → **redemander l'angle manquant** plutôt que de
conclure. Un verdict sur des photos incomplètes le dit (« vue arrière absente : contrefort
non évalué ») — jamais de conclusion sur une zone qu'on n'a pas vue.

## 3. Grille de lecture de l'état

Regarder, pour chaque chaussure, et **justifier visuellement** (ce qu'on voit, où) :

| Élément | Ce qu'on cherche |
|---|---|
| Gomme / crampons | zones lissées, crampons arrondis ou arrachés, mousse ou plaque visible à travers la gomme |
| Mousse intermédiaire | plis marqués et profonds sur le flanc, compression asymétrique, perte de rebond décrite par l'athlète |
| Contrefort (talon) | affaissement, talon qui penche vers l'intérieur ou l'extérieur sur surface plane |
| Tige | déchirures, coutures ouvertes, trou au bout ou sur le flanc |

Verdict global, un seul, avec la couleur ET les mots :

| Couleur | `condition` | Sens |
|---|---|---|
| 🟢 | `green` | rien d'inquiétant, usure normale pour le kilométrage |
| 🟡 | `yellow` | usure visible, à surveiller, prochaine inspection dans ~100-200 km |
| 🟠 | `orange` | usure avancée : gomme lisse par endroits, mousse ridée, ou tige abîmée |
| 🔴 | `red` | fin de vie visible : plaque/mousse exposée, contrefort effondré, tige percée |

Le verdict est une **lecture de photos**, pas une mesure : dire ce qui manque pour être
plus sûr. La décision de retirer la paire reste à l'athlète (le coach conseille).

## 4. Comparaison avec l'inspection précédente — le signal le plus fiable

Avant de conclure, lire l'historique de la paire (`inspections` ci-dessus, ou les fichiers
`gear/*_<gear_id>_inspection.md`). Une **deuxième inspection** d'une même paire contient
toujours une comparaison explicite : « talon gauche plus usé qu'au 2026-08-02 (+180 km) »,
« plis de la mousse inchangés », « état stable ». Renseigner `previous` (chemin de
l'inspection précédente) et dire si l'état s'est dégradé plus vite que le kilométrage ne
le laissait attendre. C'est plus fiable qu'un verdict isolé, car on compare une chaussure
à elle-même, avec le même angle de prise de vue.

## 5. Indices de foulée depuis la zone d'usure

Un **indice**, à formuler comme tel (« l'usure suggère… », « cela fait penser à… »).
Synthèse du projet, inspirée de sources grand public (voir « Sources » en fin de page) — approximation du projet,
pas un protocole clinique :

| Zone d'usure principale | Indice (`gait_hints`) | Remarque |
|---|---|---|
| Talon postéro-latéral | `heel_strike` — attaque talon | fréquent et normal |
| Milieu du pied latéral, talon peu usé | `midfoot_forefoot_strike` — attaque médio/avant-pied | **les sources divergent** : Marathon Handbook lit une usure latérale du médio-pied comme une foulée neutre — le formuler avec encore plus de prudence |
| Talon médial (intérieur) | `pronation_hint` — indice de pronation | à croiser, très dépendant du modèle |
| Avant-pied latéral fort | `supination_hint` — supination à la propulsion | à croiser |

Dans la conversation, écrire « indice de pronation », jamais une étiquette portée sur
l'athlète. Le bloc `arc` ne garde que les valeurs de `gait_hints`.

**Asymétrie gauche/droite : à mettre en avant.** Comparer les deux semelles zone par zone :
`asymmetry.level` (`none`, `mild`, `marked`) et `asymmetry.side` (le côté le plus usé).
Une asymétrie peut venir de la foulée, d'une différence de longueur de jambe, de l'histoire
de blessures… ou simplement d'un terrain camboré (route, chemin en dévers) — le dire.

## 6. Croiser avec le reste du dossier de l'athlète

- **Historique de blessures et douleurs** : `medical/` (fichiers `*_health.md`, champ
  `pain`), section blessures du profil. Une usure asymétrique côté gauche et une douleur
  déclarée au genou gauche sont un **rapprochement**, pas une cause établie.
- **Dynamiques de course du FIT (temps de contact au sol, équilibre G/D)** : **indisponible**
  dans ce dépôt. Le pipeline FIT (`skills/fit-download`, `scripts/arc_samples.py`) n'extrait
  pas ce champ et aucun KPI du projet ne l'exploite. Le dire honnêtement s'il est demandé ;
  **ne jamais l'inventer ni le déduire**. La cadence, elle, existe mais ne dit rien de l'appui.
- **Source de données (`[data].source`)** : rien de spécifique à Garmin ici ; le kilométrage
  de la paire vient de `arc_index.py gear`, qui lit les fichiers `activities/`, quelle que soit la source.

## 7. Garde-fous

- L'usure est un **signal faible** : chaussures modernes (pile haute, rocker, mousses
  techniques) et terrains (trail, cailloux, bitume) la déforment. Toujours formulée comme un
  **indice**, **jamais un diagnostic** — ni de la foulée, ni d'une blessure, ni d'un défaut
  biomécanique.
- **Aucune mesure en mm sans référence d'échelle** dans la photo (pièce, règle). Sans échelle :
  décrire qualitativement (« crampons arrondis »), n'écrire ni `lug_depth_mm` ni un chiffre.
  Avec échelle : `scale_reference: true` et une valeur approximative, avec sa marge. Le
  contrat refuse `lug_depth_mm` sans `scale_reference`.
- **Ne jamais recommander de changer de technique de foulée** sur la seule base d'une photo.
  Si une piste semble utile (asymétrie marquée, douleur associée), renvoyer vers un
  professionnel (§8), pas vers un exercice correctif ni un changement d'attaque de pied.
- Ne jamais promettre qu'une paire « tiendra » N km de plus : on décrit ce qu'on voit.
- Aucune photo dans le dépôt public : elles vivent dans `gear/photos/` du workspace
  (gitignoré). Ne jamais les republier, ni les envoyer ailleurs.
- Respecter `[language].documents` pour tout ce qui est écrit dans `gear/` (français par défaut).

## 8. Relais médical

Une **asymétrie marquée** (`asymmetry.level: marked`) ou un **lien plausible avec une douleur
déclarée** est transmis à l'agent `medical` **uniquement s'il figure dans `[agents].enabled`**
(prompt en anglais, ajouter « Respond in <langue des documents> ») avec : le fichier
d'inspection, la douleur concernée, l'historique de blessures. Sinon, ne pas l'appeler et ne pas
le mentionner : suggérer un **kiné** ou une **analyse de foulée en laboratoire**, en une phrase,
sans rien affirmer sur la cause. Une douleur ≥ 7/10 suit le seuil de consultation déjà défini
pour `/log` (`[injury_risk].pain_consult_threshold`).

## 9. Persistance

`gear/AAAA-MM-JJ_<gear_id>_inspection.md` — charger d'abord le skill `workspace-data-contract`
(section `gear_inspection`) : bloc ```` ```arc ```` `kind: gear_inspection` (`date`, `gear_id`,
`condition`, `distance_m` lu dans `arc_index.py gear`, `wear_zones`, `asymmetry`, `gait_hints`,
`photos`, `previous`, `scale_reference`), puis en français : justification visuelle, comparaison
avec la précédente, indices de foulée, ce qui n'a pas pu être évalué. Puis valider :

```bash
python3 scripts/arc_index.py --validate gear/AAAA-MM-JJ_<gear_id>_inspection.md
```

**Photos.** Si l'image est disponible comme fichier, la copier dans
`gear/photos/AAAA-MM-JJ_<gear_id>_<vue>.jpg` (`semelles`, `profil`, `arriere`, `tige`) et la
citer dans `photos`. Si elle n'est qu'affichée dans la conversation et ne peut pas être
enregistrée, **laisser `photos` absent et le dire** — ne jamais citer un chemin qui n'existe pas.
Le dossier `gear/` est gitignoré, mais un workspace privé versionné (`git_autocommit`) embarque
son contenu : des photos redimensionnées (~1 Mo) suffisent.

Après l'écriture, `python3 scripts/arc_index.py` met à jour le tableau de bord (vue Matériel,
carte « Inspections photo »).

## 10. Bilan de carrière d'une paire retirée

Quand une paire passe en `(retirée)` (l'athlète le déclare, ou le coach édite la puce à sa demande) :

```bash
python3 scripts/arc_index.py gear-career --gear ID
```

Le JSON donne le kilométrage total (départ compris), les séances, la période, les **courses**
(séances dont l'intensité planifiée du jour est `race`), les meilleurs efforts (seulement sur les
séances à splits — la clé est absente sinon, ne pas l'inventer), la plus longue sortie, la
dernière inspection et l'historique des états. Présenter un **court résumé** (5-6 lignes) et,
si l'athlète le souhaite, le garder dans `rapports/AAAA-MM-JJ_bilan_<gear_id>.md` (`report_type: adhoc`).
Proposer une dernière inspection si la paire n'en a jamais eu : ce sera la référence de la suivante.

## Sources

- Doctors of Running, « Outsole Wear Patterns » : https://www.doctorsofrunning.com/footwear-science-outsole-wear-patterns/
- Marathon Handbook, « Wear on running shoes » : https://marathonhandbook.com/wear-on-running-shoes/
- Tout le reste (cadence de 200 km, seuils de couleur, table d'indices simplifiée) est une
  **approximation du projet**, pas une norme.
