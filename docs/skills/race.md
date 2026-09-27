# Course (`/race`)

`/race` donne le compte à rebours de votre objectif actif, le score Trail
Shape (#63, un indicateur parmi d'autres) et le plan de course (#59) s'il en
existe un. Il n'écrit ni ne modifie jamais un plan/plan de course, et ne
pousse rien vers Garmin.

## Lancer

```
/race
```

## Ce qui est répondu

Le compte à rebours (`objective.days_left`) et le score viennent de
`python3 scripts/arc_index.py trail-shape`, dont **chaque** valeur de
`status` est gérée explicitement :

| `status` | Réponse |
|---|---|
| `no_objective` | `Course — aucun objectif actif (planning/active_objective.md absent ou incomplet).` |
| `incomplete_objective` | Compte à rebours si connu, score indisponible (distance/dénivelé manquant — jamais deviné) |
| `race_past` | `Course — la course est passée (J+<jours>) : voir un débrief plutôt qu'une préparation.` |
| `race_too_short` | Compte à rebours conservé, score non applicable à cette distance |
| `ok` | Première ligne fixe : `Course — J-<objective.days_left> <nom de la course>, Trail Shape <score>` |

- Le détail de l'objectif (distance, dénivelé) et, selon `[coaching].verbosity`,
  les composantes du score Trail Shape — avec un `data_confidence` `"low"`
  toujours signalé explicitement, jamais présenté comme un verdict certain.
- Le plan de course existant (`kind: "race_plan"`), s'il y en a un — nommé,
  jamais recalculé ici.

## Ce qu'il ne fait jamais

- Il n'écrit ni ne modifie aucun plan/plan de course — c'est le rôle de
  l'agent `course-strategist`.
- Il ne pousse rien vers Garmin.
- Il ne présente jamais un score Trail Shape de faible confiance comme un
  verdict certain.

## Fichier source

`skills/race/SKILL.md`
