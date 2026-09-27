# Semaine (`/week`)

`/week` donne le statut compact de la semaine en cours — réalisé, prévu,
restant, et le verdict des garde-fous — sous forme de tableau court. **Lecture
seule** : ne modifie pas le plan, ne pousse rien vers Garmin.

## Lancer

```
/week
```

## Ce qui est répondu

- Première ligne fixe : `Semaine — <réalisé>/<prévu>, garde-fous : <ok|bloqué|à surveiller>`.
- Un tableau compact, une ligne par séance : date, type, statut
  (`done`/`planned`/`skipped`/`cancelled`), charge.
- Le verdict `scripts/arc_guardrails.py check` en un mot — pour l'explication
  complète d'un blocage, utiliser [`/why`](why.md).

Sensible à un plan multi-semaines (#113) : la commande utilise le sélecteur
adéquat plutôt que de reparser les fichiers à la main quand plusieurs fichiers
semaine couvrent la date du jour.

## Ce qu'il ne fait jamais

- Il ne modifie ni ne réécrit aucun fichier semaine.
- Il ne pousse rien vers le calendrier Garmin.
- Il ne propose pas d'ajustement — c'est le rôle de l'agent `coach` en session
  normale.

## Fichier source

`skills/week/SKILL.md`
