# Safety case

The users are minors and the data is health data, so safety rules are hard-coded,
not left to the LLM. Each claim below names the mechanism and the evidence.

| Claim | Mechanism | Evidence |
| --- | --- | --- |
| No plan ever breaks a hard safety rule | CP-SAT hard constraints H1-H7; independent checker `hard_violations()`; template fallback | 0 violations in all plans and executed weeks over 3 x 25 players x 40 weeks (`docs/evaluation/report.md`); 60 randomised planner tests |
| The LLM cannot weaken safety | LLM output is a schema-validated `ConstraintSet` of soft constraints only; extra fields rejected | Adversarial scenarios (skip match, hard MD-1, 4 speed sessions in PHV) pass; schema tests |
| No diagnosis, no counselling by the agent | Pain, red mood and missed check-ins with red readiness escalate to a named adult; agents take no action for that player | Scenario suite categories pain/red mood/missed (17 cases); API test: red check-in reaches physio queue, notified in < 1 s |
| Re-plans never add load | Per-day RPE ceiling from the current plan | Planner model; simulator executed-week checks |
| Coaches can override plans but not past hard rules | Edits are re-checked with `hard_violations()`; rejected with 422 | API test `test_coach_edit_cannot_break_hard_rules` |
| Risky changes are approved by a human | Fixed Coordinator policy table; anything not listed goes to the coach | `tests/test_flags_coordinator.py` |
| Growth-spurt players are protected | Mirwald estimate; speed RPE ≤ 6; plyometric drills filtered out | Planner and dev-coach tests; scenario suite (8 PHV cases) |
| Late maturers aren't judged against early maturers | Bio-banded percentiles on the player card and for goals | `analytics/norms.py` |
| No "will you make it pro" prediction, no weight-loss features | Not built; prompts forbid predictions | Code review |
| Works when the LLM is down | Rule-based constraints and explanations | Scenario suite "LLM API down" (5 cases) |
| Data rights | Consent per data type (guardian below 16), export, delete | API tests for consent, export, delete |
| Security | Field-level encryption, RBAC + scope checks, audit log on every health read | API tests (RBAC, audit); `test_health_fields_are_encrypted_at_rest` |
| Transparency | Every change has a "Why?" card (data chips + approver) and an audit-log entry | E2E test: tired player sees the card with the coach's name |

## Known limitations

- **Readiness weights** (0.40/0.35/0.25) are team defaults, not from a study. A ±0.1
  shift changes 15% of daily bands, above the plan's 10% robustness target. Options:
  hysteresis on band changes, or calibrating the weights against staff ratings.
- **ACWR** is a weak injury predictor; it is one flag among several, and injury
  results from the simulator are secondary (synthetic injury model, three variants).
- **Test norms** in `backend/config/norms.yaml` are placeholders and must be replaced
  with published academy norms before real use.
- The **Mirwald** maturity offset has a standard error of about 0.5 years.
- All demo data is **synthetic**; no real player data is stored.
