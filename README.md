# PathToPro

Agent system that watches each academy player's load, growth, recovery and
development, then rebuilds next week's plan before problems happen. Coaches
approve risky changes.

**Design principle:** code computes, the LLM plans and explains, a fixed policy decides who approves.

## Status

| Plan week | Deliverable | State |
| --- | --- | --- |
| 1 | Data model, autonomy policy, simulator spec | Done: `backend/domain/models.py`, `backend/agents/coordinator.py`, `backend/simulator/config.yaml` |
| 2-3 | Analytics engine + simulator | Done: `backend/analytics/`, `backend/simulator/` (70 tests) |
| 3-5 | Backend API, auth, consent, audit | Not started |
| 5-7 | CP-SAT planner + agent loop | Not started (Coordinator policy done) |
| 4-10 | Frontend (player PWA, coach view) | Not started |

## Quick start

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
pytest                        # unit tests + doctests
python -m simulator --out data/season              # baseline season, load-driven injuries
python -m simulator --variant readiness --out data/season_readiness
```

The simulator writes `players`, `daily`, `sessions`, `checkins`,
`anthropometrics`, `tests` and `injuries` CSVs and prints season metrics.

## Layout

```
pathtopro/
  backend/
    analytics/   # sRPE, EWMA ACWR, monotony, strain, Mirwald, readiness, norms, risk flags
    agents/      # Coordinator autonomy policy (agent loop, Planner, Dev Coach to come)
    config/      # readiness weights, test norms (placeholders) - editable per club
    domain/      # SQLAlchemy 2 models (22 entities) and shared enums
    simulator/   # synthetic season generator with pluggable planning policy
    eval/        # season metrics (evaluation harness to come)
    tests/
  docs/          # scope decisions, open questions
```

All demo data is synthetic. No real player data is stored.
