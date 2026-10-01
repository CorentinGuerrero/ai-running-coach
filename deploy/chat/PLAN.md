# Coach chat — implementation plan (draft, to validate)

Status: **plan only**. Nothing below is implemented. The visual target is the static
prototype `web/chat-prototype.html` (scripted replies, no model call).

**Decisions (2026-09-29):**
- Same host as the dashboard, under `/api/chat` — hardened as described in §2.4.
- The chat service runs on the **coach machine** (next to `garmin-mcp`, tokens, workspace).
- Options A (Claude) and B1 (OpenAI-compatible via OpenCode) are built **in parallel**,
  behind the same mock-first frontend.
- Users who move to OpenRouter can run the chat *and* the daily-sync cron on it (§5).
  `[chat]` and `[sync]` stay **independent** (each keeps its best setup);
  `install.sh --llm …` configures both at once and warns before replacing a runner.
- Garmin changes can also be approved **from the phone notification** (§2.8).
- Default models: DeepSeek on OpenRouter; on Claude, **Sonnet 5.5 for the chat, Haiku 4.5
  for the cron** — confirmed or corrected by the evaluation set (§3, §5.4).

## 1. Goal and non-goals

**Goal:** a "Coach" page next to the read-only dashboard, behind the **same SSO**
(Traefik + Authentik/Authelia middleware), where the athlete talks to the coach staff
with the same agents, skills, MCP tools, guardrails and Markdown persistence as in the IDE.

**Non-goals (v1):**
- No use of the Claude Pro/Max or ChatGPT subscription (not allowed for third-party
  front-ends — see `docs/mobile.md`). Remote Control stays the free, subscription-based
  option.
- No multi-user: one athlete per workspace, as today.
- No change to the read-only dashboard's security model (it stays `:ro`, strict CSP).

## 2. Shared architecture (identical for both backends)

```
browser ──HTTPS──▶ Traefik ──(auth middleware: Authentik)──┬─▶ dashboard  (arc_serve.py, ro)   /, /api/*
                                                          └─▶ coach-chat (new service, rw)   /api/chat/*
                                                                 │
                                                                 ├─ ChatBackend: "claude" | "openai"
                                                                 ├─ workspace (rw) + ~/.garminconnect
                                                                 └─ garmin MCP (stdio child process)
```

### 2.1 Frontend
- `web/chat.html` + `web/js/chat.js` + `web/css/chat.css` (no inline code, the dashboard CSP
  stays as is). Nav item "Coach" added to `renderNav` only when `[chat].enabled = true`.
- Same origin → `connect-src 'self'` is enough; Traefik routes `PathPrefix(/api/chat)` to
  the chat service, **with the same auth middleware** as the dashboard router.
- Right panel "Ce que voit le coach" reuses existing dashboard endpoints (`/api/today`,
  week, settings) — no new data API.

### 2.2 Chat service `scripts/arc_chat.py` (new process / container)
- Python, `asyncio` HTTP server (candidate: Starlette + uvicorn; to confirm, the dashboard
  is stdlib-only on purpose, the chat service can't be because of the SDKs).
- **Separate from `arc_serve.py`** so the dashboard keeps no write access and no API key.
- Endpoints:
  | Method | Path | Role |
  |---|---|---|
  | `POST` | `/api/chat/sessions` | new conversation → `session_id` |
  | `GET` | `/api/chat/sessions` | list (title, date, cost) |
  | `POST` | `/api/chat/sessions/{id}/messages` | send a message; response = **SSE stream** |
  | `POST` | `/api/chat/sessions/{id}/approvals/{approval_id}` | `{"decision": "allow"\|"deny"}` |
  | `POST` | `/api/chat/sessions/{id}/interrupt` | stop the running turn |
  | `GET` | `/api/chat/healthz` | health check |

### 2.3 Backend-agnostic event protocol (SSE)
The frontend only knows these events; each backend adapts to them:

| Event | Payload | UI |
|---|---|---|
| `text_delta` | `{text}` | streamed paragraph |
| `tool_start` / `tool_end` | `{id, name, summary, ok}` | collapsible "N étapes" trace |
| `approval_request` | `{approval_id, tool, human_summary, diff}` | confirmation card (Apply / Refuse) |
| `file_written` | `{path}` | file chip (link to dashboard route when known) |
| `usage` | `{input, output, cache_read, cost_eur}` | cost counter |
| `done` / `error` | `{reason}` | unlock composer / error banner |

### 2.4 Security and permissions (one policy, enforced by both backends)
- **Same-host routing, hardened:**
  - Traefik router `Host(<dashboard host>) && PathPrefix(/api/chat)`, **mandatory** auth
    middleware — compose refuses to start without `TRAEFIK_AUTH_MIDDLEWARE`, exactly like
    the dashboard router (`${VAR:?}`); no published port.
  - The chat service runs on the coach machine: if Traefik is on another host, it reaches
    it through a Traefik *file provider* service over the LAN/Tailscale; `arc_chat.py`
    binds only to that interface and rejects any source IP other than Traefik's
    (`[chat].trusted_proxies`). If Traefik is on the same machine: bind `127.0.0.1`.
  - CSRF (the SSO cookie is ambient): every state-changing request must carry a custom
    header (`X-ARC-Chat: 1`, not settable cross-site without CORS) and pass an
    `Origin`/`Sec-Fetch-Site: same-origin` check; no CORS headers at all.
  - Allowed `Host` values checked like the dashboard (`ARC_DASHBOARD_ALLOWED_HOSTS`).
  - Rate limit per user (turns/minute) on top of the budget guard.
- **Identity:** trust the forward-auth header (`X-authentik-username` / `Remote-User`) only
  when the request comes from the Traefik network; reject if missing or not in
  `[chat].allowed_users`. Defence in depth — Traefik remains the real gate.
- **Tools policy** (`config/chat-policy.toml`, versioned):
  - auto-allowed: read workspace files, Garmin/intervals **read** tools, `resources/`.
  - auto-allowed with path allowlist: write/edit only under `activities/ medical/ nutrition/
    planning/ rapports/`.
  - **approval required:** every Garmin/intervals **write** tool (`schedule_workouts`,
    `schedule_week`, `delete_workout(s)`, `upload_course`, `upload_workout(s)`,
    `add_weigh_in`, `create_event`, `update_event`, `delete_event`…). Approval times out
    (e.g. 10 min) → treated as deny.
  - allowed scripts only through a dedicated tool (`arc_index.py`, `arc_log.py`,
    `arc_race_pacing.py`, `analyze_gpx.py`, `download_fit.py`), never a free shell.
  - web access: only the domains the skills need (wttr.in, OSM Overpass).
- **Refusals are traced:** a denied proposal updates the decision file
  (`outcome: rejected_by_athlete`), consistent with the existing decision contract.
- **Secrets:** API keys only via env vars / Docker secrets, never in `workspace*.toml`.
- **Budget guard:** `[chat].daily_budget_eur` — the service refuses new turns once reached
  and says so; per-turn `max_turns` cap.

### 2.5 Configuration (new `[chat]` section, same resolution rule as the rest)
```toml
[chat]
enabled = false
backend = "claude"            # "claude" | "openai"
model = "claude-sonnet-5-5"   # or an OpenRouter/OpenAI-compatible model id
base_url = ""                 # openai backend only (OpenRouter, Mistral, Ollama, vLLM…)
api_key_env = "ANTHROPIC_API_KEY"   # name of the env var, never the key
daily_budget_eur = 2.0
max_turns = 30
allowed_users = []            # empty = anyone Traefik lets through
trusted_proxies = ["127.0.0.1"]
ntfy_approvals = true         # push an "Ouvrir" button for pending approvals (§2.8)
ntfy_quick_approve = false    # direct Appliquer/Refuser buttons, opt-in (§2.8)
```
`[chat]` is independent from `[sync]` (§5). `install.sh --llm …` writes both.

### 2.6 Persistence
- Conversations: `.arc/chat/<session_id>.jsonl` (gitignored, derived, disposable like the
  SQLite index). **Not** in the data-contract folders.
- Everything the coach decides still lands in Markdown with its ```` ```arc ```` block,
  validated by `arc_index.py --validate` — the chat adds no new source of truth.
- After a turn that wrote files: trigger the dashboard reindex (existing background
  reindex) so the dashboard reflects changes immediately.

### 2.7 Behaviour rules carried over
- `[agents].enabled`, `[health].morning_check`, `[language].*`, `[coaching].*`, `[data].source`
  apply unchanged (they're read by the agents from `AGENTS.md` + config, not by the chat).
- `/today`, `/why`, `/week`, `/race`, `/log` exposed as quick buttons; the service sends
  them as plain prompts (skills already handle them).
- No `/coach-setup` suggestion loop in the chat (same exemption as short commands) — the
  page shows a static hint instead if the profile is missing.

### 2.8 Approving from the phone notification (ntfy)

An approval request that isn't answered in the page within a few minutes (or when no
browser tab is open) is also sent as a push notification with action buttons.

- **Default — "Ouvrir" button (ntfy `view` action):** opens
  `https://<host>/chat.html#approval=<id>` in the browser; SSO applies as usual, one tap
  on "Appliquer" in the page. No new attack surface.
- **Opt-in — direct "Appliquer / Refuser" buttons (ntfy `http` action),
  `[chat].ntfy_quick_approve = true`:** the ntfy app can't carry the SSO cookie, so these
  buttons POST to `/api/chat/approve/<token>` on a **dedicated Traefik router without the
  SSO middleware**, restricted to that exact path and method, and rate-limited. The token is:
  - random, single-use, expires in 30 min;
  - HMAC-bound to the approval id **and** a hash of the exact tool payload (a token can't
    approve a different change);
  - stored hashed server-side; replay, expiry and payload mismatch are rejected and logged.
  If that bypass router is judged too risky for a given setup, the default `view` mode
  stays available.
- **Content minimisation:** the notification text contains only the change summary
  ("Mardi : fractionné → EF 45 min"), never health values — ntfy topics may live on a
  public server.
- **Async approval:** the chat turn waits ~10 min for an answer, then ends with the
  proposal *pending* (persisted). An approval arriving later **resumes the session** with
  "athlete approved proposal X"; the agent then pushes, and the tool call is auto-allowed
  only for the payload hash that was approved. Expired/refused → decision file updated
  (`rejected_by_athlete` / `expired`).
- **Later extension (not v1):** the headless cron could use the same mechanism to *propose*
  a change after the morning check (today it never pushes), approved from the phone.
- Relies on `scripts/notify.sh` / `[notifications]` (ntfy URL, auth token) already in place;
  ntfy action buttons to be checked against the ntfy version in use.

## 3. Option A — Claude (Anthropic API) via the Claude Agent SDK

**Principle:** the Agent SDK *is* the Claude Code harness as a library. It loads the
project's `.claude/agents`, skills, `.mcp.json` and `CLAUDE.md`/`AGENTS.md` exactly like
the IDE → near-100 % behavioural parity, sub-agent delegation included.

- Package: `claude-agent-sdk` (Python). Auth: `ANTHROPIC_API_KEY` (or Bedrock/Vertex
  credentials). **No subscription OAuth.**
- Key options (names **to verify against the SDK docs at implementation time**,
  `code.claude.com/docs/en/agent-sdk`):
  - `cwd=<workspace>`, `setting_sources=["project"]` → loads agents/skills/MCP config.
  - `can_use_tool` callback → maps to `approval_request`, awaits the user's decision
    (asyncio future + timeout). This is where `chat-policy.toml` is enforced.
  - `allowed_tools` / `disallowed_tools` → remove `Bash`, restrict `WebFetch`.
  - `include_partial_messages=True` → `text_delta`.
  - `resume=<sdk_session_id>` → continue a conversation across page reloads.
  - result message cost/usage → `usage` event and budget guard.
- Model: configurable. **Default for the chat: Sonnet 5.5** ($2 / $10 per MTok, cache read
  $0.20). Haiku 4.5 ($1 / $5) is only half the price and the chat is where the hard work
  happens — multi-agent delegation, the medical safeguards, plan changes, pushing workouts
  to Garmin — so a cheap model making a wrong call costs more than the saving.
  Haiku 4.5 becomes the chat default only if it passes the whole evaluation set; it is the
  default for the **cron** (§5.4), a repetitive, well-specified job.
  Prompt caching is handled by the harness.
- Runtime: the SDK drives the Claude Code CLI binary → container needs it (check whether
  the Python wheel bundles it or Node is required). `garmin-mcp` runs as today.
- **Pros:** no agent loop to write; exact parity with the IDE; skills/agents unchanged;
  best tool-use quality on these prompts (they're written and tested for Claude).
- **Cons:** Claude-only; per-token billing; bigger image (CLI runtime).
- **Rough cost (estimate, to measure in PoC):** a coaching exchange with a few tool calls
  over a ~30 k-token cached prefix ≈ **€0.03–0.10 on Sonnet 5.5**, ~2× on Opus 5.5.

## 4. Option B — OpenAI-compatible providers (OpenRouter, OpenAI, Mistral, Ollama…)

Writing our own agent loop + MCP client + skill loader + sub-agent delegation would be a
re-implementation of a harness. Recommended instead:

### B1 (recommended) — OpenCode server as the harness
- `install.sh --ide opencode` already deploys `.opencode/agents` and `.opencode/skills`
  (symlinks) and the MCP entry in `opencode.json` → the project is already OpenCode-ready.
- Run OpenCode in **server mode** on the coach machine/container (HTTP API + event stream,
  sessions, permission prompts). `arc_chat.py` becomes a thin **adapter**: OpenCode events
  → our SSE protocol; OpenCode permission requests → `approval_request`.
- Provider configured in a **project-local** `opencode.json` for the chat service (not the
  user's global one): OpenRouter (`base_url` + key), or any OpenAI-compatible endpoint.
- Permissions: OpenCode's `permission` config (`edit`, `bash`, per-MCP-tool patterns)
  set to mirror `chat-policy.toml` (writes to Garmin = `ask`, bash = `deny`).
- **To verify in PoC:** exact server API and event names (pin the OpenCode version, the
  API moves fast), skill loading parity, sub-agent (`task`) behaviour, how usage/cost is
  reported per provider.
- **Pros:** any model; no loop to write; already wired in the repo.
- **Cons:** one more runtime (Node/Bun binary); API less stable than the Anthropic SDK;
  prompt caching depends on provider/model; quality varies a lot by model.

### B2 (fallback) — minimal own loop
`openai` SDK (chat completions + tool calling) + Python MCP client + our own file tools,
agents/skills injected as system prompt. Only if B1 is blocked; high maintenance.

### Model caveats for option B
- Require models with solid function calling and ≥128 k context.
- Weaker models are likely to break the `arc` contract, skip the morning-check triptych or
  soften medical guardrails → **the PoC must include a small evaluation set** (below) and
  the config should document "tested" models only.
- Claude through OpenRouter works but is ~the same price + OpenRouter fee and loses some
  cache efficiency → if the model is Claude, use option A.

## 5. OpenRouter (or any provider) for the daily-sync cron too

Today the cron (`scripts/daily-sync.sh`, `[sync].runner`) runs `claude -p` or
`codex exec` **on the subscription**. A user who moves to OpenRouter should be able to
run the cron on it as well — one key, one bill.

### 5.1 Separate settings, one install flag
`[chat]` and `[sync]` stay **independent**, so each can use its best setup (e.g. chat on
Sonnet 5.5 through the API, cron still on the Claude subscription — or both on OpenRouter).

```toml
[sync]
runner = "opencode"           # claude | codex | opencode (new)
model = "deepseek/…"          # opencode only — exact OpenRouter id pinned during the PoC
base_url = ""                 # opencode + non-OpenRouter OpenAI-compatible endpoint
api_key_env = "OPENROUTER_API_KEY"
daily_budget_eur = 0.5
```

`install.sh --llm openrouter [--model …]` (and `--llm anthropic`) writes **both**
sections in `workspace.user.toml`:
- `[chat]`: backend + model.
- `[sync]`: `runner = "opencode"` (or `claude` + API key for `--llm anthropic`) + model.
- If `[sync].runner` was already set to something else, it is **replaced with a warning**
  that names the old and new value and how to go back
  (`⚠ [sync].runner : claude → opencode (abonnement → OpenRouter). Pour revenir : …`).
  Same for `[chat]`. Nothing is changed silently.
- The key goes in an env file with `600` permissions loaded by the cron/launchd and chat
  services — never in TOML, never in the shell profile.
- No cron reinstall needed: `daily-sync.sh` reads the runner at each run.

### 5.2 New cron runner `opencode`
- `daily-sync.sh --runner opencode` → `opencode run` (headless, one-shot) in the workspace,
  with a **project-local** OpenCode config generated for the sync (provider, model, garmin
  MCP, permissions: file edits allowed in data folders, Garmin writes **denied** — the sync
  never pushes workouts, bash denied).
- Prompt: `/garmin-daily-sync` if OpenCode resolves project commands/skills in headless
  mode, otherwise the skill body inlined like the `codex` runner already does.
- Output contract unchanged: final ```` ```resume ```` block → ntfy; `ERREUR : …` first line
  on Garmin token failure, so the existing 401 detection keeps working. Provider-side
  failures (bad/expired OpenRouter key, 402 out of credits) get their own notification
  text — never confused with a Garmin 401 (same rule as the Codex 401 today).
- `watch` mode (`garmin_watch.py`) is untouched: it stays LLM-free and only calls the
  runner when there's something new — the best cost lever on a paid provider.
- `coach_doctor.py`: new checks — runner/model consistency, key env var present (never
  printed), provider reachable (models list call, no tokens spent), OpenCode version pinned.

### 5.3 Anthropic API for the cron (`--llm anthropic`)
`claude -p` works with `ANTHROPIC_API_KEY`. **Caveat:** that variable breaks Remote
Control (`docs/mobile.md`: "Remote Control requires claude.ai subscription auth"), so the
key is injected **only** into the sync and chat services' environment. `daily-sync.sh`
loads it from the env file just before running the command.

### 5.4 Default models and cost

| | OpenRouter | Claude (API) |
|---|---|---|
| Chat | DeepSeek (latest chat model, id pinned in PoC) | **Sonnet 5.5** |
| Cron | DeepSeek | **Haiku 4.5** |

- **Why Haiku 4.5 for the cron:** the sync is repetitive and tightly specified (fetch missing
  dates, write files to the contract, `resume` block), and `arc_index.py --validate` catches
  contract breaks. If Haiku fails the cron scenarios, fall back to Sonnet 5.5.
- **DeepSeek caveats:**
  - Tool-calling reliability over a long agent run is the main risk → the model must pass
    the evaluation set before it becomes the documented default.
  - **Health data:** chat and cron send HRV, sleep and injury data to the model. On
    OpenRouter, restrict the providers to ones that don't train on or keep the data
    (provider routing / data-policy settings), and document this in `docs/`.
    Using DeepSeek's own API directly is not recommended here.
- **Rough cost (estimate, to measure):** one sync run ≈ a few Garmin calls + 2–4 file writes
  over a ~30 k-token prefix → a few cents on Haiku 4.5, less on DeepSeek; 2 runs/day ≈ a
  few €/month at most. `watch` mode usually runs fewer LLM passes than fixed `times`.
- Budget guards stay per section (`[chat].daily_budget_eur`, `[sync].daily_budget_eur`);
  the cron skips its run and notifies instead of going over.
- A validation failure after an `opencode` run is reported in the ntfy summary — a weak
  model silently breaking the `arc` contract every night is worse than a failed run.

### 5.5 Open point to verify
OpenRouter also exposes an **Anthropic-compatible** endpoint (usable by Claude Code via
`ANTHROPIC_BASE_URL`). If confirmed and stable, `claude -p` could run on OpenRouter too —
keeping the Claude Code harness for the cron. Not relied upon in this plan; checked during
the PoC only.

## 6. Delivery steps (after validation)

1. **Frontend shell** — `chat.html/js/css` from the prototype, wired to a **fake backend**
   (`backend = "mock"`) that replays scripted SSE events. Lets us finalise the UX and the
   protocol without spending tokens.
2. **Chat service skeleton** — endpoints, SSE, sessions `.jsonl`, identity header check,
   budget guard, `chat-policy.toml`, Traefik route + compose service (`rw` workspace
   mount, secrets).
3. **Adapters in parallel** — A (Agent SDK) and B1 (OpenCode server), both validated on
   the same evaluation set (B1 on 2–3 models).
4. **Phone approvals** — ntfy `view` action first, then the opt-in signed quick-approve
   route (§2.8), async approval resume.
5. **Cron on OpenRouter** — `opencode` runner, `[sync]` model/key settings, doctor checks,
   `install.sh --llm` with replace-and-warn (§5).
6. **Docs** — `docs/dashboard/chat.md` (FR), `configuration.md` `[chat]`, `mobile.md` update
   (the "pas de front maison" warning becomes "front maison = clé API"), the
   `opencode` runner, OpenRouter data-policy advice in `configuration.md` / `mobile.md`.
7. **Tests** — policy engine (allow/ask/deny per tool and path), SSE protocol, identity
   check, budget guard, compose lint (like `tests/lint/test_docker.py`); adapters tested
   with recorded event streams (no live API in CI); `daily-sync.sh --runner opencode
   --dry-run` command construction and auth-failure classification with stubs, like the
   existing `codex` runner tests; approval tokens (single use, expiry, payload binding,
   replay); `install.sh --llm` replace-and-warn.

### Evaluation set (PoC, both options)
5–8 scripted scenarios run against a fixture workspace, checked automatically where
possible: morning check with low readiness (triptych present, session downgraded, decision
file written and valid), `/log` with unknown product (must ask), pain ≥ 7/10 (consultation
recommended), Garmin push (approval requested, nothing written before approval), `/week`
factual answer (no `/coach-setup` suggestion), language setting respected; plus 3 cron
scenarios (nothing new → no write; new activity → valid file + `resume`; Garmin 401 →
`ERREUR` line). Models run: Sonnet 5.5, Haiku 4.5, DeepSeek.

## 7. Open questions for validation

1. Is the opt-in quick-approve route (§2.8, a Traefik router without SSO but with signed
   single-use tokens) acceptable, or keep only the "Ouvrir" button?
2. Daily budget defaults: `[chat]` €2, `[sync]` €0.5 — OK?
3. Start the PoC now with step 1 (frontend + mock backend)?
