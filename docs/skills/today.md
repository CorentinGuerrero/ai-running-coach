# Aujourd'hui (`/today`)

`/today` répond en une ligne à « qu'est-ce que je fais aujourd'hui ? » — la
séance du jour, le bilan matinal au niveau configuré (`[health].morning_check`),
et le créneau météo si la séance est en extérieur. **Lecture seule** : ne
valide rien, ne modifie rien, ne pousse rien vers Garmin.

## Lancer

```
/today
```

## Ce qui est répondu

- Une **première ligne fixe**, verdict d'abord : `Aujourd'hui — <séance prévue / repos / à ajuster>`.
- La séance du jour (type, durée/distance, intensité) telle qu'elle figure
  dans le fichier semaine courant (`planning/Semaine_*.md`).
- Le bilan matinal au niveau configuré :
  - `full` (défaut) : HRV + FC de repos + readiness, les trois ensemble.
  - `minimal` : readiness seule, en une ligne — jamais de HRV ni de FC de repos.
  - `off` : aucune donnée de santé n'est récupérée.
- Le créneau météo optimal (matin tôt / midi / soir), uniquement si la séance
  du jour est en extérieur.

La longueur de la réponse suit `[coaching].verbosity` (`brief`/`standard`/`detailed`).

## Ce qu'il ne fait jamais

- Il ne pose pas de question.
- Il n'écrit ni ne modifie aucun fichier.
- Il n'appelle jamais `schedule_workouts`/`schedule_week`/`upload_workout`.
- Il ne propose pas `/coach-setup`, même sur une installation neuve — c'est une
  question factuelle, pas un premier démarrage.

## Fichier source

`skills/today/SKILL.md`
