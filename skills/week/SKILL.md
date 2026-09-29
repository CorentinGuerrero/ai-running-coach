---
name: week
description: Short command — invoked as /week. Compact status of this week's plan (done/planned/remaining load, guardrail status) as a table/list. Never writes a plan/week/decision file and never pushes to Garmin. Load when the user runs /week or asks for a status of the current week.
gemini_command: "true"
---

# `/week` — compact status of the current week

Thin wrapper: no new planning logic. Reports the current week's sessions with
their status and the load, plus the guardrail verdict, in a short table. It
never writes or edits a plan/week/decision file, and never calls a Garmin
write tool.

## Configuration read first

`config/workspace.toml` / `config/workspace.user.toml` — `[language].responses`
(falls back to `[language].documents` when `auto` and the command is invoked
bare), `[coaching].verbosity`, `[agents].enabled`, `[athlete].units`.

## Finding the current week

Find the week file(s) by `kind: "week"` inside `planning/*.md` — **never** by
a filename pattern such as `Semaine_*.md`: a multi-week plan (#113) may name
its file after its first Monday while covering several weeks in one `weeks`
array, so filename matching alone can miss the week that actually covers
today. Once the file is found, run:

```bash
python3 scripts/arc_guardrails.py check --week <file> [--week-start <lundi de la semaine du jour>]
```

Pass `--week-start` explicitly whenever the resolved file could contain more
than one week (a `weeks` array, #113) so the guardrail check targets the
Monday that actually covers today, rather than whichever week the command
defaults to. A single-week file needs no `--week-start`.

## Delegation

If `coach` is enabled **and** a `task`/subagent tool is available, delegate to
**`coach`**, English prompt + "Respond in <language>":

> Report the status of the week covering today (see the week-selection rule
> above — find it by `kind: "week"`, not by filename). For each session in
> that week: date, type, status (one of the contract's `SESSION_STATUS`
> values — `planned`, `done`, `missed`, `moved`, `cancelled` — never any other
> word), and its load contribution (duration or distance). Sum done vs
> planned load. Then run `python3 scripts/arc_guardrails.py check --week
> <file> [--week-start <date>]` and report its verdict as a single status
> word (ok / block / warn-info / input error — see `agents/coach.md`'s
> guardrails section for the three real outcomes plus the CLI's own input-
> error exit code), never a full re-explanation (that is `/why`'s job). Do
> not modify the week file or write a new plan/week/decision file, do not
> push anything to Garmin, do not propose changes — only report facts already
> on record. Finally run `python3 scripts/arc_index.py gear` and, only if a
> non-retired pair is over its alert threshold (`alert`) or at ≥ 90 % of it
> (`near_threshold`), add one line « Chaussures : <nom> <km>/<seuil> km » per
> such pair (« seuil dépassé » when over) — nothing at all otherwise. Same rule for
> `python3 scripts/arc_index.py equipment` (#134): one « Matériel : <nom> <valeur>/<seuil> » line
> per non-retired item with `alert` or `near_threshold` (« seuil dépassé » when over) — nothing otherwise.

If `coach` is not enabled, or if you cannot delegate at all (no `task`/
subagent tool available, e.g. running as a bare Gemini CLI command), find the
week file(s) and run the guardrails check yourself, plus the same
`arc_index.py gear` line rule as above, and the `arc_index.py equipment` (#134) line rule.

## Output contract

**First line, fixed shape** — start with the translated word for "Week"
(French default: "Semaine"), optionally wrapped in Markdown emphasis or
preceded by a heading marker, then an em dash/en dash/hyphen, then the status:

```
Semaine — <réalisé>/<prévu> (unité selon [athlete].units), garde-fous : <ok|bloqué|à surveiller|entrée invalide>
```

`garde-fous : entrée invalide` covers the guardrails CLI's own input-error
exit code (bad JSON, missing `week_start`…) — distinct from a real `block`
verdict, never conflated with it.

Then, respecting `[coaching].verbosity` (`brief` = the table only, `standard`/
`detailed` add a short comment per flagged session):

A compact table, one row per session:

| Date | Type | Statut | Charge |
|---|---|---|---|

**Shoe line (#132)** — after the table, one « Chaussures : … » line per non-retired
pair over its threshold (« seuil dépassé ») or at ≥ 90 % of it, from
`python3 scripts/arc_index.py gear` (`alert`/`near_threshold`). Omit the line
when no pair qualifies; it is derived mileage, never a plan change.

**Equipment line (#134)** — same discipline for gear beyond shoes: one « Matériel : … » line per
non-retired item with `alert`/`near_threshold` in `python3 scripts/arc_index.py equipment`
(trigger value/threshold in its own unit: km, h, séances, jours). Omit it when nothing qualifies;
never invent a threshold for an item that declares none.

No week file found for the current week: say so in one line rather than
inventing sessions or falling back to a past/future week silently.
