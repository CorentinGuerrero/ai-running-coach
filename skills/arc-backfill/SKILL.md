---
name: arc-backfill
description: Met au contrat de données (bloc ```arc) les fichiers du workspace écrits avant lui — activités, santé, météo, semaines, nutrition, rapports. Travaille par lots à partir de la liste produite par scripts/arc_index.py backfill-plan, sans rien inventer et sans perdre le texte existant. Charger quand l'utilisateur lance /arc-backfill, ou quand le tableau de bord signale des données incomplètes.
---

# Backfill du contrat de données

Les fichiers écrits avant le contrat n'ont pas de bloc ```arc. Le tableau de bord
les lit quand même, au mieux, mais ce qu'il en tire est partiel : pas de
splits, pas de verdict, des nombres reconnus à la volée. Ce skill les réécrit au
contrat, un lot à la fois.

## 1. Obtenir la liste

```bash
python3 scripts/arc_index.py backfill-plan
```

La commande réindexe le workspace et écrit `.arc/backfill.md`, en **deux
sections distinctes** :

- **« Fichiers hors contrat »** : un fichier par ligne, avec ce qui lui manque.
  La liste tient déjà compte de la configuration — en `[health].morning_check
  = "off"`, un fichier santé sans HRV n'y figure pas. C'est la section que ce
  skill traite (étape 2 ci-dessous).
- **« Collisions de semaine » (#69)** : des fichiers `planning/Semaine_*.md`
  **déjà valides** au contrat, mais dont une semaine est éclipsée par un autre
  fichier qui décrit la même semaine (`week_start`) — un fichier dédié et un
  plan multi-semaines (`weeks[]`) qui la recouvre, le plus souvent. **N'y
  touchez pas avec ce skill** : ce n'est jamais un bloc ```arc à réécrire (il
  est déjà correct), l'action est de RETIRER l'entrée `weeks[]` en trop (ou de
  supprimer le fichier entier s'il ne couvre plus que des semaines déjà
  décrites ailleurs) — voir `skills/workspace-data-contract/SKILL.md`, section
  « week », pour le détail de la règle de priorité. Signalez-les à l'athlète
  sans les traiter dans ce lot.

Si les deux sections annoncent **0 fichier**, dites-le en une ligne et
arrêtez-vous.

## 2. Traiter un lot

Prenez **au plus 10 fichiers** par passe, les plus récents d'abord : ce sont
eux qui pèsent dans la courbe de forme (42 jours).

Pour chaque fichier :

1. Chargez le skill `workspace-data-contract` (une fois par passe) et lisez le
   fichier **en entier**.
2. Construisez le bloc ```arc avec **ce que le fichier dit**. Convertissez en SI
   (« 12,4 km » → `12400`, « 1 h 12 » → `4320`). Une valeur que le fichier ne
   donne pas reste absente — ne la déduisez pas, ne l'estimez pas.
3. Une valeur absente mais récupérable chez Garmin (identifiant d'activité,
   splits, HRR) ne se récupère que si l'utilisateur l'a demandé pour ce lot, en
   respectant `garmin-sync-efficiency` : une date à la fois, jamais de plage.
4. Insérez le bloc **sous le titre**. Ne supprimez, ne reformulez et ne
   traduisez rien du texte existant.
5. Validez :

   ```bash
   python3 scripts/arc_index.py --validate activities/2026-03-03_trail.md
   ```

   Corrigez jusqu'à `ok`.

## 3. Rendre compte

Relancez `python3 scripts/arc_index.py backfill-plan` et donnez :

- le nombre de fichiers traités dans ce lot, et ceux laissés de côté avec la
  raison (fichier illisible, valeur contradictoire…) ;
- le nombre de fichiers restants.

Proposez le lot suivant ; ne l'enchaînez pas sans accord. Réécrire l'historique
de l'athlète est une opération qu'il doit pouvoir relire : s'il versionne son
workspace (`git_autocommit`), suggérez-lui de committer avant de continuer.
