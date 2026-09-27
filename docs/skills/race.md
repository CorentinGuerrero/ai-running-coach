# Course (`/race`)

`/race` donne le compte à rebours de votre objectif actif, le score Trail
Shape (#63, un indicateur parmi d'autres) et le plan de course (#59) s'il en
existe un. **Lecture seule** : n'écrit, ne planifie ni ne pousse rien.

## Lancer

```
/race
```

## Ce qui est répondu

- Première ligne fixe : `Course — J-<jours restants> <nom de la course>, Trail Shape <score>`.
- Sans objectif actif ou objectif incomplet (`planning/active_objective.md`
  absent, vide, ou sans distance/dénivelé), le dit explicitement plutôt que de
  deviner un score.
- Le détail de l'objectif (distance, dénivelé) et, selon `[coaching].verbosity`,
  les composantes du score Trail Shape.
- Le plan de course existant (`kind: "race_plan"`), s'il y en a un — nommé,
  jamais recalculé ici.

## Ce qu'il ne fait jamais

- Il n'écrit ni ne modifie aucun plan de course — c'est le rôle de l'agent
  `course-strategist`.
- Il ne pousse rien vers Garmin.
- Il ne présente jamais un score Trail Shape de faible confiance comme un
  verdict certain.

## Fichier source

`skills/race/SKILL.md`
