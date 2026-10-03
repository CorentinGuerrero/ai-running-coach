---
name: intervals-icu-best-practices
description: Use when creating, updating, or troubleshooting Intervals.icu events or workouts via the Intervals.icu MCP tools (create_event/update_event/delete_event/bulk_create_events on eddmann/intervals-icu-mcp, installed by `./install.sh --source intervals` — #68). Covers the real (verified) tool payloads — no workout_doc parameter on create_event/update_event, targets expressed as text in `description` — idempotency via get_calendar_events (no upsert exists), and verify-after-push on the fields get_event actually returns. Primary push target when `[data].source = "intervals"`, secondary (on explicit request) otherwise.
---

# Intervals.icu MCP Tool — Best Practices (#68, verified against eddmann/intervals-icu-mcp @ cb91d4a)

Everything below was read directly from the server's source — modules
event_management.py, events.py, client.py and response_builder.py of
eddmann/intervals-icu-mcp, commit `cb91d4a` (pinned in `install.sh` as
`INTERVALS_MCP_REF`). Nothing here is a hypothesis or a forum quote — if the
pinned commit changes, re-verify this file against the new source before
trusting it again.

## Tools

- `create_event(start_date, name, category, description?, event_type?, duration_seconds?, distance_meters?, training_load?)` — new event. `category` is one of `WORKOUT`/`NOTE`/`RACE`/`GOAL`. **No `event_id` parameter — this is never an upsert.**
- `update_event(event_id, name?, description?, start_date?, event_type?, duration_seconds?, distance_meters?, training_load?)` — `event_id` is REQUIRED and must already exist (404 otherwise). Only the fields you pass change.
- `delete_event(event_id)`
- `bulk_create_events(events)` — `events` is a **JSON string** (not a list) containing an array of objects, each needing at least `start_date_local`, `name`, `category`.
- `get_calendar_events(days_ahead?, days_back?)` — planned events in a window (default: today → +7 days). Returns them grouped by date.
- `get_upcoming_workouts(limit?)` — same data, filtered to `category == "WORKOUT"` only, sorted, capped at `limit`.
- `get_event(event_id)` — single event detail.

## CRITICAL: there is no `workout_doc` parameter

An earlier draft of this skill (predating #68) described a `workout_doc`
JSON-steps parameter on `add_or_update_event`. **That tool does not exist on
the server this project installs.** `create_event`/`update_event`'s Python
signatures (verified above) accept only the fixed fields listed — there is
no way to pass structured steps to either of them. Do not invent one.

`bulk_create_events` is different: its `events` argument is raw JSON text,
and the tool forwards each object's extra keys **unfiltered** to the real
Intervals.icu API (`client.bulk_create_events` does `POST .../events/bulk
json=events_data` — no field allowlist). So a `"workout_doc": {...}` key
inside a `bulk_create_events` item may well be accepted server-side (the
Intervals.icu platform itself supports structured workout docs). **But this
MCP server never reads it back**: neither `bulk_create_events`'s own response
mapping nor `get_event`/`get_calendar_events` ever include a `workout_doc`
field (verified: their result-building code only extracts
id/date/name/category/description/type/metrics/fitness_context/color/external_id).
**Never rely on a value you cannot verify was accepted as sent** — see
GUARDRAILS-style discipline elsewhere in this project (`agents/coach.md`).
Treat `workout_doc` on `bulk_create_events` as **unsupported for this
project**, not merely undocumented — nothing here can confirm it landed.

## Expressing structured targets (#60 personal targets) in `description`

Since no field survives the round trip except `description` (plain text,
confirmed present on `create_event`/`update_event`/`bulk_create_events`
inputs AND on `get_event`/`get_calendar_events` outputs), encode a session's
structure and targets there, one line per element, using this project's own
convention (not an Intervals.icu native syntax — say so if the athlete asks):

```
Endurance 60 min — Z2
Cible allure : 5:30-5:50 /km
Cible FC : 140-150 bpm
Matériel : chaussures route
```

- **Pace target** (`pace_target.speed_low_ms`/`speed_high_ms` from
  `scripts/arc_workout_targets.py`, see `agents/coach.md` → "Personal targets
  (#60)"): convert m/s to a min/km range for the `Cible allure :` line —
  never paste the raw m/s value, the athlete reads pace, not speed.
- **HR target** (`hr_target.bounds_bpm`, low then high): `Cible FC : LOW-HIGH bpm`.
- **Heat-adjusted pace (#171):** on a hot/🔴 day run the targets command with
  `--heat`; when `heat_adjustment.applies` and `intensity_maintained`, write the
  `Cible allure :` line from `pace_target.adjusted` (or `declared_pace.adjusted_pace_s_km`)
  — the HR line stays unchanged — and add a `Chaleur : …` line with
  `heat_adjustment.step_note`. For `reschedule_*` actions do not create the
  event as planned: propose the alternative, create it after confirmation.
- **Hill-repeat D+ lower bound** (`hill_repeats.per_rep.elevation_gain_m`):
  `≥ X m D+ par répétition` — same "lower bound, not a centered prediction"
  rule as `garmin-workout-scheduling`/`agents/coach.md`.
- A `null` target value (see `agents/coach.md` → "Key the drop-the-target rule
  on the VALUE being `null`") means: omit that line entirely, never write a
  placeholder or an invented number.
- Strength sessions: one line per exercise (`sets x reps @ weight`), same
  spirit as the Garmin `RepeatGroupDTO` detail requirement, just as text.

## Idempotency — no upsert exists, check before every push

There is no `event_id` lookup-by-date-and-name and no upsert semantics
anywhere on this server (unlike Garmin's `workout_id` reuse pattern in
`garmin-workout-scheduling`). Before pushing a session for a given date:

1. Call `get_calendar_events(days_back=0, days_ahead=<enough to cover the
   date>)` (or `get_upcoming_workouts` if you only need workouts) for the
   date range you are about to write.
2. If an event already exists on that date with a matching `name` (or
   `category == "WORKOUT"` and it's clearly the same planned session):
   - Same session, unchanged → do nothing (idempotent no-op).
   - Session changed → `update_event(event_id=<its id>, ...)` with the new
     fields — `event_id` comes from the `id` field the calendar listing just
     returned, never guessed or reused across dates.
3. If no matching event exists → `create_event(...)`, and read the `id` the
   response returns (`data.id` — see envelope shape below) for the
   verification step.

Re-running `create_event` for an already-planned date WITHOUT this check
creates a duplicate — there is no server-side deduplication.

## Verify after push — only on fields `get_event` actually returns

After `create_event`/`update_event`, call `get_event(event_id)` (the id you
just got back) and confirm ONLY the fields it actually returns:
`id`, `date` (`start_date_local`, note the renamed key), `name`, `category`,
`description`, `type`, and — nested under `metrics` — `distance_meters`,
`duration_seconds`, `training_load`, `intensity_factor`, `joules`,
`joules_above_ftp`. **Never assert on `workout_doc`, steps, or any structured
field — `get_event` does not return one.** For a `bulk_create_events` push,
verify similarly via `get_calendar_events` for that date range (its response
lists the same reduced field set per event).

## Response envelope (every tool, verified in `response_builder.py`)

```json
{"data": {...}, "metadata": {"fetched_at": "...", "query_type": "..."}}
```

An error response has the shape `{"error": {"message": "...", "type": "...",
"timestamp": "..."}}` instead — no `data` key at all when it fails.

## Working examples

Create a simple planned run:

```json
{
  "start_date": "2026-09-28",
  "name": "Endurance 60 min",
  "category": "WORKOUT",
  "event_type": "Run",
  "duration_seconds": 3600,
  "description": "Endurance 60 min — Z2\nCible FC : 140-150 bpm"
}
```

Update an existing one (only the changed fields):

```json
{
  "event_id": 123456,
  "duration_seconds": 4200,
  "description": "Endurance 70 min — Z2\nCible FC : 140-150 bpm"
}
```

Bulk-create a week (still no `workout_doc` reliance — text targets in each
`description`):

```json
[
  {"start_date_local": "2026-09-28", "name": "Endurance 60 min", "category": "WORKOUT",
   "type": "Run", "moving_time": 3600, "description": "Cible FC : 140-150 bpm"},
  {"start_date_local": "2026-09-30", "name": "Repos", "category": "NOTE"}
]
```

## Date handling

- `start_date`/`start_date_local` sets the event's date — always double-check
  it against the session you intend before calling `create_event`/`update_event`/`bulk_create_events`.
- Post-write verification (above) also confirms the date landed correctly —
  a mismatch means calling `update_event` again with the corrected date.
