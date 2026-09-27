---
name: race
description: Short command — invoked as /race. Countdown to the next objective plus a readiness summary (Trail Shape score, #63) and the race plan (#59) if one exists. Read-only. Load when the user runs /race or asks how race prep is going.
gemini_command: "true"
---

# `/race` — countdown and readiness, read-only

Thin wrapper around existing signals: the active objective's countdown, the
Trail Shape score as ONE indicator among others (never the only word on
readiness), and the race plan when `course-strategist` already produced one.
Writes nothing, plans nothing, pushes nothing.

## Configuration read first

`config/workspace.toml` / `config/workspace.user.toml` — `[language].responses`,
`[coaching].verbosity`, `[agents].enabled`, `[athlete].units`.

## Delegation

If `coach` is enabled, delegate via `task` to **`coach`**, English prompt +
"Respond in <language>":

> Read-only: run `python3 scripts/arc_index.py trail-shape` for the active
> objective's countdown (`days_left`) and Trail Shape `score` (present it as
> ONE indicator, with its `data_confidence`/`notes` when the status is not
> `"ok"` — e.g. `"no_objective"`, `"incomplete_objective"` — never silently
> upgrade a low-confidence or missing score into a confident verdict). If a
> race plan exists (`planning/*.md` with `kind: "race_plan"` for this
> objective, story #59), name it and its pace/nutrition/gear scenario count
> without re-deriving new numbers. Do not write anything, do not create or
> edit a race plan, do not push anything to Garmin.

If `coach` is not enabled, run `scripts/arc_index.py trail-shape` and look for
a `race_plan` yourself.

## Output contract

**First line, fixed prefix**, translated to `[language].responses` (French
default):

```
Course — J-<days_left> <nom de la course>, Trail Shape <score ou "indisponible : <raison>">
```

When `trail-shape`'s `status` is not `"ok"`:

- `"no_objective"`: `Course — aucun objectif actif (planning/active_objective.md absent ou incomplet).`
- `"incomplete_objective"`: keep the countdown if `days_left` is known, and say
  the score is unavailable because the distance/elevation target is missing —
  never guess it.

Then, respecting `[coaching].verbosity`:

- the countdown detail (target distance/elevation, from `active_objective.md`);
- the Trail Shape components/notes when `standard`/`detailed` (skip at `brief`);
- one line naming the race plan (scenario count, last updated) if one exists,
  or "aucun plan de course encore" — never inventing pace numbers here (that
  is `course-strategist`'s job, not this read-only summary).
