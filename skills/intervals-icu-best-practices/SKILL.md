---
name: intervals-icu-best-practices
description: Use when creating, updating, or troubleshooting Intervals.icu events or workouts via the Intervals.icu MCP tools (create_event/update_event/delete_event/bulk_create_events on eddmann/intervals-icu-mcp, installed by `./install.sh --source intervals` — #68; older examples below say add_or_update_event/get_events, see the note at the top). Covers the description-vs-workout_doc pitfall, start_date preservation, post-update verification, and tested JSON payload patterns. Primary push target when `[data].source = "intervals"`, secondary (on explicit request) otherwise.
---

# Intervals.icu MCP Tool — Best Practices

## Server & tool names (#68 — read first)

This skill's examples below (`add_or_update_event`, `get_events`, `delete_event`)
predate the project settling on a specific server. `./install.sh --source
intervals` (and the manual setup in `docs/faq.md`) install the community
server eddmann/intervals-icu-mcp (<https://github.com/eddmann/intervals-icu-mcp>),
whose actual tool names are `create_event` (new event), `update_event`
(existing `event_id`), `delete_event`, `bulk_create_events`, `get_calendar_events`
/ `get_upcoming_workouts` (post-update verification), and `get_event` (single
event detail) — see the correspondence table in `AGENTS.md`. **The workflow
below still applies unchanged** — `workout_doc` for structured content,
mandatory `start_date`, verify-after-write — only substitute the tool name:
`add_or_update_event` → `create_event` (no `event_id`) or `update_event` (with
one), `get_events` → `get_calendar_events`. Used as the SECONDARY push target
when `[data].source = "garmin"` (default, only on explicit request), or as the
PRIMARY one — via `create_event`/`bulk_create_events`, same idempotency
discipline as `garmin-workout-scheduling` — when `[data].source = "intervals"`.

## Problem Identified

When creating events via `add_or_update_event`, the `description` field appears to be stored but NOT returned in the GET response (API returns `"description": null"`).

**However**, older events (pre-March 2026) do show descriptions — this suggests either:
1. API change between calls
2. Different parameter name required now
3. Need to use `workout_doc` for structured workouts

## Solution: Use workout_doc

According to the Intervals.icu forum, the preferred method is to use `workout_doc` with structured JSON steps:

```json
{
  "category": "WORKOUT",
  "start_date_local": "2026-03-10T10:00:00",
  "type": "Ride",
  "name": "Lactate Test",
  "workout_doc": {
    "steps": [
      {
        "duration": 300,
        "power": { "units": "%ftp", "value": 90 }
      }
    ]
  }
}
```

## MCP Tool Schema

The `add_or_update_event` tool DOES accept `workout_doc` as a parameter:

```
- athlete_id (optional)
- api_key (optional)
- event_id (optional)
- start_date (optional)
- name (optional)
- workout_doc (optional) ✅
- workout_type (optional)
- moving_time (optional)
- distance (optional)
```

## Recommended Approach

1. **For simple events**: Use `description` as text — it IS stored even if not returned in GET
2. **For structured workouts**: Use `workout_doc` with proper JSON structure

## Tested Working Pattern (verified 2026)

```json
{
  "event_id": "EXISTING_ID",
  "name": "Session Name",
  "start_date": "YYYY-MM-DD",
  "moving_time": 2400,
  "workout_type": "Other",
  "workout_doc": {"description": "Details..."},
  "description": "Short details..."
}
```

Note: Use `workout_doc.description` for detailed workout content, `description` for summary.

## Date Handling Rules

- **`start_date` is REQUIRED and SETS the event date.** Always verify the intended date before calling `add_or_update_event`.
- **Post-update verification:** After ANY create/update operation, ALWAYS call `get_events` to verify the date matches the intended date. If mismatched, update again with the correct date.
- **Batch operations:** Track each update and verify completion before reporting success.

## Example — Strength Session with workout_doc

```python
workout_doc = {
  "steps": [
    {"description": "Échauffement", "duration": 600},
    {"reps": 4, "steps": [
      {"text": "Goblet Squat", "duration": 45, "weight_kg": 12},
      {"text": "Fentes Bulgares", "duration": 45},
      {"text": "Step Up", "duration": 45}
    ]}
  ]
}
```

## Manual Workaround

Since the API seems inconsistent:
1. Create the event with `description`
2. Edit manually in the Intervals.icu UI if needed
