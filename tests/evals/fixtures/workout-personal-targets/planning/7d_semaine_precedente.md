# Semaine précédente

```arc
{"arc": 1, "kind": "week", "week_start": "{{DATE}}", "location": "Tournai", "sessions": [{"date": "{{DATE}}", "sport": "trail", "title": "Séance seuil 30 min", "intensity": "threshold", "planned_duration_s": 1800, "outdoor": true, "status": "done"}]}
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
