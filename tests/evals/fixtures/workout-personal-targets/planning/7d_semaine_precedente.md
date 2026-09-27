# Semaine précédente

```arc
{"arc": 1, "kind": "week", "week_start": "{{PREV_WEEK_START}}", "location": "Tournai", "sessions": [{"date": "{{DATE}}", "sport": "trail", "title": "Séance seuil 30 min", "intensity": "threshold", "planned_duration_s": 1800, "outdoor": true, "status": "done"}]}
```

Séance seuil déjà réalisée la semaine précédente — contexte de réalité d'une
semaine mixte (endurance + seuil), jamais repoussée sur le calendrier
(`status: "done"`). Volontairement dans un fichier séparé, daté 7 jours avant
aujourd'hui (`<N>d_` — voir `tests/evals/runner.py::_materialize_relative_dates`) :
strictement antérieure à `{{WEEK_START}}` quel que soit le jour de la semaine
où tourne ce cas (7 jours avant aujourd'hui est toujours avant le lundi de la
semaine courante), pour qu'aucune séance de la semaine courante ne partage
jamais sa date — voir `tests/evals/cases/workout-personal-targets.toml` pour
pourquoi cette ambiguïté de date doit être structurellement impossible plutôt
que juste évitée par chance (revue de code #107, point 2).

`week_start` utilise `{{PREV_WEEK_START}}` (lundi de la semaine ISO
précédente), PAS `{{DATE}}` (revue de code #107, 2ᵉ tour, BLOQUANT) : `{{DATE}}`
vaut « 7 jours avant aujourd'hui », qui n'est un LUNDI que si ce cas tourne
lui-même un lundi — tout autre jour, `arc_guardrails.py check --week` rejette
un `week_start` qui n'est pas un vrai lundi (exit 2). `{{PREV_WEEK_START}}`
(`{{WEEK_START}}` moins 7 jours) est, lui, TOUJOURS un lundi, quel que soit le
jour d'exécution. `{{DATE}}` (7 jours avant aujourd'hui) tombe alors toujours
DANS la semaine de `{{PREV_WEEK_START}}` (même jour de la semaine, une semaine
plus tôt) — cohérent, jamais une séance datée hors de la semaine qu'elle
prétend documenter.
