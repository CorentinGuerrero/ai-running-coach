---
name: inspection
description: Commande courte /inspection [paire] (#149) — lancer l'inspection photo d'UNE paire de chaussures. Sans argument, liste les paires actives avec leur rappel (arc_index.py inspections) et propose la plus urgente ; avec un argument (id, nom, slug ou uuid garmin), résout la paire contre le profil et demande en cas d'ambiguïté ou de paire inconnue, jamais de devinette. Donne le protocole photo en une courte liste et la façon d'envoyer les photos (copie dans gear/photos/, chemin de fichier, image collée vue mais non enregistrable), puis charge gear-inspection pour la lecture, la comparaison et la persistance. Interactive uniquement, ne propose jamais /coach-setup, n'écrit jamais d'inspection sans photo ni description de l'usure. Charger quand l'athlète tape /inspection ou dit vouloir inspecter ses chaussures.
gemini_command: "true"
---

# `/inspection [paire]` — lancer l'inspection photo d'une paire (#149)

Ce skill n'ajoute **aucune logique de lecture** : il sert à **désigner la paire** et à
**recevoir les photos**, puis passe la main au skill `gear-inspection` (grille de lecture,
comparaison avec la précédente, garde-fous, persistance). Une inspection = **une paire**.

## Règles fixes

- **Interactive uniquement** : jamais en mode headless (`/garmin-daily-sync`), jamais
  depuis un cron — c'est une conversation avec des photos.
- **Ne propose jamais `/coach-setup`**, même sur une installation neuve (règle des commandes
  courtes, `AGENTS.md` « Premier démarrage ») : cette commande répond à une demande précise.
- **Jamais de devinette** : paire ambiguë ou inconnue → on demande, liste des candidats à
  l'appui.
- **Jamais d'écriture d'un fichier `gear/…_inspection.md` sans photo ni description écrite de
  l'usure** fournies par l'athlète dans cette conversation.
- Respecter `[language].responses` ; les fichiers écrits restent en `[language].documents`.
- Aucune donnée de santé n'est lue : indépendant de `[health].morning_check` et de `[data].source`.

## Sans argument — `/inspection`

```bash
python3 scripts/arc_index.py inspections --unreferenced-photos
```

1. **Aucune paire déclarée** (`gear` vide) : le dire en une ligne et renvoyer vers la syntaxe du
   profil (`planning/Runner_Profile.md`, « Matériel & lieux » → `### Chaussures`, une puce par
   paire, par exemple `- Nike Pegasus — id: pegasus (par défaut)`) ou, pour reprendre les paires
   déjà connues de Garmin, vers la **simulation** `python3 scripts/garmin_gear_backfill.py`
   (elle ne modifie rien sans `--apply`). Ne rien inventer.
2. Sinon, lister en quelques lignes les **paires actives** (ni `retired`, ni `ignored`, ni
   `unknown`) avec leur rappel, formulé selon `due_reason` — jamais la même phrase pour les trois :
   - `interval` → « ≈ N km depuis la dernière inspection » ;
   - `never_inspected` → « jamais inspectée (N km au compteur) » ;
   - `threshold_alert` → « a franchi son seuil d'alerte : inspection conseillée avant de la retirer » ;
   - `due: null` (`baseline_unknown`) ou `due: false` → « pas de rappel » (la paire reste inspectable à la demande).
3. **Proposer la plus urgente** (alerte de seuil, puis la plus grosse `km_since_inspection_m`),
   et attendre l'accord de l'athlète : c'est une proposition, jamais une obligation.
4. Si `unreferenced_photos` n'est pas vide : le signaler (« j'ai trouvé N photos dans
   `gear/photos/`, à quelle paire appartiennent-elles ? ») — voir « Boîte de dépôt » ci-dessous.

## Avec argument — `/inspection pegasus`

Résoudre l'argument contre les paires du **profil** (sortie de `arc_index.py gear` et de
`inspections`), dans cet ordre, sans casse ni accents :

1. un `id:` explicite (`gear_id`) identique ;
2. le nom de la paire (égalité, puis inclusion du texte dans le nom) ;
3. le slug du nom (`arc_contract.gear_slug`) ;
4. l'uuid `garmin:` de la paire.

- **Une seule correspondance** → la paire est désignée, l'annoncer (« Inspection de <nom> »).
- **Plusieurs correspondances** (deux Pegasus, par exemple) **ou aucune** → demander, en listant
  les candidats (nom, `id`, kilométrage) ; ne jamais choisir à la place de l'athlète, ne jamais
  créer une paire à partir de l'argument.
- **Paire `(retirée)`** : le dire. Proposer d'abord le **bilan de carrière**
  (`arc_index.py gear-career --gear ID`, voir `gear-inspection` §10) ; une dernière inspection
  reste possible si l'athlète la veut (référence de la suivante).
- **Paire `(ignorée)`** : le dire — elle n'est pas suivie, donc pas de rappel ; n'inspecter que sur
  insistance explicite de l'athlète.

## Le protocole photo, en une liste courte

Une fois la paire désignée, donner **une seule liste** (reprise de `gear-inspection` §2) :

1. les deux **semelles à plat** (dessous), lumière rasante ou de face ;
2. une **vue latérale** à hauteur de semelle, par chaussure ;
3. une **vue arrière** sur surface plane ;
4. la **tige** (dessus) ;
5. une **pièce ou une règle** dans le cadre (sans elle, aucune mesure en millimètres).

## Comment envoyer les photos

Dire en quelques lignes, sans promettre ce qu'on ne peut pas vérifier :

- **Chemin recommandé, valable quel que soit le client** : copier les photos (n'importe quel nom
  de fichier) dans `<workspace>/gear/photos/`, puis écrire « c'est fait » — ou donner le chemin
  de chaque fichier. Le coach les repère, les renomme et les cite dans l'inspection.
- **Terminal Claude Code** : donner le **chemin du fichier** dans la conversation.
- **Image collée dans la conversation** : le modèle la **voit**, donc l'inspection est possible,
  mais elle **ne peut pas être enregistrée** comme fichier : `photos` reste absent du fichier
  d'inspection, et le dire.
- **Téléphone / Remote Control** : envoi d'images **à valider** (`docs/mobile.md`) — ne jamais le
  promettre ; proposer le chemin ci-dessus (copie dans `gear/photos/` par la synchronisation de
  fichiers du téléphone ou `scp`, puis `/inspection` depuis le téléphone), ou une description écrite de l'usure.

## Boîte de dépôt `gear/photos/`

Les images de `gear/photos/` **non citées** par une inspection indexée sont des candidates
(`unreferenced_photos` de la commande ci-dessus — calcul, pas devinette). Règles :

- Si la paire n'est pas évidente (plusieurs paires, plusieurs séries de photos) → **demander à
  quelle paire** elles appartiennent.
- Les **renommer** en `AAAA-MM-JJ_<gear_id>_<vue>.<ext>` (`semelles`, `profil`, `arriere`, `tige` ;
  extension d'origine conservée, extensions raster du contrat seulement : `.jpg` `.jpeg` `.png`
  `.webp`), **dans `gear/photos/` uniquement**, puis les citer dans `photos`.
- **Ne jamais supprimer** une photo, **ne jamais déplacer** un fichier hors de `gear/photos/`.

## Puis

Charger le skill **`gear-inspection`** : lecture des photos (grille 🟢🟡🟠🔴), comparaison avec
l'inspection précédente de la même paire, indices de foulée (jamais un diagnostic), relais
`medical` seulement s'il est dans `[agents].enabled`, persistance dans
`gear/AAAA-MM-JJ_<gear_id>_inspection.md` (charger `workspace-data-contract` avant d'écrire) et
validation `python3 scripts/arc_index.py --validate <fichier>`. Sans photo **ni** description de
l'usure : ne rien écrire, redemander.
