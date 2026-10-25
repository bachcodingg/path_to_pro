# Architecture

One Python backend, one React frontend, one database. `docker compose up --build`
runs everything (PostgreSQL, API, web) and seeds the synthetic demo season.

```
 Player PWA ─┐                         ┌─ analytics/   pure metric functions (no LLM)
 Coach web  ─┼─ React app ── /api ── FastAPI ── agents/  Monitor · Planner · Dev Coach · Coordinator
 Physio     ─┤   (Vite, Tailwind,      │     │          └─ llm.py: Claude + cache + rule fallback
 Guardian   ─┘    Recharts, SVG)       │     └─ planner/   OR-Tools CP-SAT weekly model
                                       ├─ APScheduler: nightly 23:00 run
                                       └─ PostgreSQL (SQLAlchemy 2, Alembic, Fernet-encrypted health fields)
```

## Design principle

**Code computes, the LLM plans and explains, a fixed policy decides who approves.**

| Step | Who | Where |
| --- | --- | --- |
| Load, ACWR, monotony, readiness, maturity, percentiles, flags | Deterministic code | `analytics/`, `agents/monitor.py` |
| Turn flags + goals into soft constraints and weights | LLM (schema-validated), else rules | `agents/planner_agent.py`, `agents/rules.py` |
| Build the week, never breaking hard rules | CP-SAT | `planner/model.py` |
| Who approves | Fixed policy table | `agents/coordinator.py` |
| Explain to player (3 sentences) and coach (1 line) | LLM, else templates | `agents/planner_agent.py` |
| Choose drills from the curated library | LLM with a `search_drills` tool, else rules | `agents/dev_coach.py` |

## Agent cycle (one player)

1. **Monitor** runs on every check-in and nightly. It saves a `DailyStatus` (readiness,
   band, ACWR, maturity offset, flags, data chips). Safety flags (pain, red mood,
   missed check-ins with red readiness) create an `Escalation` for the player's named
   staff contact immediately. The agents take no further action for that player.
2. **Planner** runs on Sunday night (or whenever the week has no plan): the plan is
   activated and logged. On other nights it runs only when the Monitor raises a *new*
   recovery or load flag; it re-plans the rest of the week with a per-day RPE ceiling,
   so a re-plan can only make days easier.
3. **Coordinator** compares the proposed days with the current plan, classifies the
   change (intensity, load cut, load increase > 10%, session swap, match minutes) and applies the policy
   table: auto-apply, auto-apply + notify, coach approval, or escalate.
4. **Development Coach** runs after a test day: weakest bio-banded KPIs become 4-week
   goals (coach approves); drill suggestions are auto-applied.

**Readiness colours.** The band uses a safety-first buffer (hysteresis): a better
colour needs the score 8 points past the boundary, a worse colour applies at once.
Staff record their own judgement ("How ready does he look?") in the heatmap; the
Calibration page fits the weights that agree best with staff (weighted kappa, player-
grouped cross-validation), only accepting weights that catch at least as many staff-red
days, and a coach applies them (`analytics/calibration.py`, `api/services/calibration.py`).

Every run writes an `AgentRun` (inputs, flags, constraints, solver result, decision)
and `AuditLog` rows; the coach's "Match commentary" renders them in plain language.

## Planner model (CP-SAT)

- Variables per day: session type (one-hot), target RPE, match minutes (0/30/45/60/90).
- Hard rules H1-H7: fixtures fixed, ≥1 rest day, MD-1 RPE ≤ 4, no speed above RPE 6
  in the PHV window, weekly load ≤ cap when ACWR > 1.5, no session on exam evenings,
  RPE ranges per session type. Also: re-plans respect the current plan's RPE ceiling.
- Soft: hit the club's weekly load (limited to chronic × 1.3), **projected EWMA ACWR
  ≤ 1.4 on every planned day** (linear in planned loads), goal sessions, two rest days,
  easy MD+1, variety, preferred days, and the LLM's weighted constraints.
- LLM constraints with weight ≥ 8 start as hard; if infeasible they are dropped
  lowest weight first; if still infeasible (or the solver fails) a safe template is used.
- Single worker, fixed seed: the same input always gives the same week. ~0.05 s per
  player-week.

## LLM integration

`agents/llm.py` calls Claude (`claude-opus-5-5`, override with `PATHTOPRO_MODEL`)
through `messages.parse` with Pydantic output models, server-side refusal fallbacks,
and a manual tool loop for the Development Coach. Every answer is validated; one
retry with the validation error, then rules. A disk cache (`backend/llm_cache/`)
stores answers so demo scenarios replay offline. `PATHTOPRO_LLM=off` runs pure rules.

## Data and security

- 22 plan entities + accounts, notes, task completions, daily status, settings.
- Health columns use `EncryptedFloat/Int/Bool/Str/JSON` (Fernet, key from
  `PATHTOPRO_FIELD_KEY`); stored values are ciphertext.
- JWT auth, role check on every endpoint, scope check per player (own data,
  guardian's children, staff's squad).
- Every read of health data writes an `AuditLog` row.
- Consent per data type; players under the age of digital consent (16) need a
  guardian's consent. Revoked data types are neither stored nor used by the agents.

## Repository

```
backend/   api/ domain/ analytics/ planner/ agents/ simulator/ eval/ migrations/ tests/
frontend/  src/player/ src/coach/ src/physio/ src/guardian/ src/shared/ e2e/
docs/      architecture, safety case, demo script, evaluation, screenshots
```
