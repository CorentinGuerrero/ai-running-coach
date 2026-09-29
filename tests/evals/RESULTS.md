# Résultats du palier C

Dernier relevé des évals d'exécution. **Versionné volontairement** : une
régression de comportement se lit alors dans un diff de PR, pas dans la couleur
d'un job qui a déjà défilé.

Régénérer :

```bash
ARC_LLM_TESTS=1 python3 tests/run_tests.py --tier c --repeat 3
```

## Dernier relevé

| | |
|---|---|
| **Date** | _jamais exécuté_ |
| **Modèle** | `claude-haiku-4-5-20251001` (défaut) |
| **Runner** | `claude -p` |
| **Répétitions** | 3 par scénario |
| **Seuil de réussite** | 2/3 |

| Scénario | Réussites | Verdict |
|---|---|---|
| `course-strategist-carbs-target` | — | — |
| `daily-sync-green-no-why` | — | — |
| `daily-sync-red-why` | — | — |
| `daily-sync-resume-block` | — | — |
| `doctor-token-expiring` | — | — |
| `equipment-kit-attribution` | — | — |
| `feedback-with-fit` | — | — |
| `feedback-without-fit` | — | — |
| `gear-correction` | — | — |
| `gear-suggestion-three-pairs` | — | — |
| `gear-sync-conflict-athlete-wins` | — | — |
| `gear-sync-garmin-attached` | — | — |
| `gear-sync-unmapped-not-attributed` | — | — |
| `gear-write-needs-confirmation` | — | — |
| `guardrail-block-red-verdict` | — | — |
| `guardrail-ok` | — | — |
| `health-full-triad` | — | — |
| `health-minimal-readiness-only` | — | — |
| `health-off-no-health-file` | — | — |
| `health-off-no-hrv` | — | — |
| `health-own-baseline` | — | — |
| `health-token-expired` | — | — |
| `injury-risk-pain` | — | — |
| `itra-index-lookup-confirm` | — | — |
| `itra-index-privacy` | — | — |
| `log-freeform` | — | — |
| `log-freeform-unknown-product` | — | — |
| `no-medical-no-delegation` | — | — |
| `race-countdown-trail-shape` | — | — |
| `race-debrief` | — | — |
| `race-gear-missing-head-torch` | — | — |
| `race-plan-personal-model` | — | — |
| `setup-first-run` | — | — |
| `setup-idempotent` | — | — |
| `setup-prefill-garmin` | — | — |
| `setup-prefill-garmin-error` | — | — |
| `setup-prefill-garmin-morning-off` | — | — |
| `sleep-debt` | — | — |
| `sport-road-no-elevation` | — | — |
| `sport-trail-elevation` | — | — |
| `style-exigeant-names-the-miss` | — | — |
| `style-factuel-quiet` | — | — |
| `sync-activity-arc-fields` | — | — |
| `sync-declared-fuel` | — | — |
| `sync-intervals-source` | — | — |
| `sync-writes-arc-block` | — | — |
| `today-morning-check-minimal` | — | — |
| `today-morning-check-off` | — | — |
| `today-outdoor-full` | — | — |
| `trail-shape` | — | — |
| `week-status-compact` | — | — |
| `why-explains-logged-decision` | — | — |
| `workout-personal-targets` | — | — |

> **Pas encore de relevé.** Le harnais est complet et validé — scénarios,
> fixtures, serveur MCP factice, journal des appels d'outils — mais aucune
> exécution réelle n'a encore eu lieu : cela demande un runner authentifié.
> Lancez la commande ci-dessus, ou le workflow `Évals` depuis l'onglet Actions,
> puis remplacez ce tableau par le relevé obtenu.

<!-- Régénéré via `python3 tests/evals/render_results.py --results <(echo '{}')`
     (#66, revue de code) : `today-outdoor-full`, `today-morning-check-off`,
     `today-morning-check-minimal`, `why-explains-logged-decision`,
     `week-status-compact` et `race-countdown-trail-shape` ont été ajoutés par
     cette régénération. Date et modèle remis à `_jamais exécuté_`/« défaut »
     à la main après régénération : aucune exécution réelle n'a eu lieu. -->
