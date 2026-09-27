# Pourquoi (`/why`)

`/why` explique la dernière décision du coach (ou une décision nommée) à
partir du **journal des décisions** (`planning/*_decision_*.md`, #54) — jamais
une raison inventée. Si rien n'est enregistré, il le dit plutôt que de deviner.

## Lancer

```
/why
/why hier
/why cotes
/why 2026-09-20
```

Sans argument, la décision **active** la plus récente (`outcome` `applied` ou
`proposed`) est expliquée. Avec un argument : une date, un mot-clé qui
correspond au `<slug>` du fichier, ou une partie de son contenu.

## Ce qui est répondu

- Première ligne fixe : `Pourquoi — <résumé de la décision>` (ou « aucune
  décision trouvée »).
- Le déclencheur (`trigger`) et les règles de garde-fou concernées (`rule_ids`),
  si présentes.
- Les données clés qui ont justifié la décision (`inputs`).
- Ce qui a changé (`before` → `after`) pour la séance concernée.
- Le statut de la décision (`outcome`) : `applied`, `proposed` (rien n'a encore
  été poussé), `rejected_by_athlete` ou `superseded`.

## Ce qu'il ne fait jamais

- Il n'invente jamais une raison à partir d'une simple alerte ou impression
  qui n'a pas été tracée dans un fichier `decision`.
- Il n'écrit ni ne modifie aucun fichier.

## Fichier source

`skills/why/SKILL.md`
