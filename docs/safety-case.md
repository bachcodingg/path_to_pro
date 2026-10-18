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
| Readiness colours don't flicker, and warnings are never delayed | Safety-first colour buffer: a better colour needs the score 8 points past the boundary, a worse colour applies at once | Day-to-day colour changes 58% -> 44% of days; `tests/test_calibration.py` |
| Weight changes can't hide red days | Calibration only accepts weights whose red recall vs staff ratings is at least the current weights'; a coach reviews and applies; every change audited | `tests/test_calibration.py`, API test `test_staff_rating_and_calibration` |

## Known limitations

- **Readiness weights** (0.40/0.35/0.25) are team defaults, not from a study. Staff can now
  rate players and calibrate the weights in the app (Calibration page). On the synthetic
  season, the colour buffer plus calibrated weights lowers the ±0.1 sensitivity from 15.0%
  to 13.0%, still above the plan's 10% target. The cause is that the components sit at
  different levels (HRV is centred at 50 by the plan's formula, a normal night's sleep
  scores about 80), so moving weight between them shifts every score. Tested options that
  pass the target: re-centring the HRV score so a normal day scores like the other inputs
  (65-70 instead of 50), optionally with a 3-day rolling lnRMSSD average (Plews et al.).
  These give 8-10% sensitivity but cut red days from about 14% to 2-7%, so they change what
  "red" means and should be decided with real staff ratings, not synthetic ones.
- **Calibration data** in the demo is synthetic (simulated staff judgements). Real gains
  depend on real ratings; the app needs at least 60 rated days before suggesting weights.
- **ACWR** is a weak injury predictor; it is one flag among several, and injury
  results from the simulator are secondary (synthetic injury model, three variants).
- **Test norms** in `backend/config/norms.yaml` are placeholders and must be replaced
  with published academy norms before real use.
- The **Mirwald** maturity offset has a standard error of about 0.5 years.
- All demo data is **synthetic**; no real player data is stored.
- The **sensitivity** failures are concentrated on borderline days: 91% of the bands that
  flip under a +/-0.1 weight shift were within 5 points of a colour boundary (the
  evaluation now reports this), and a +/-0.05 shift changes 7.5% of bands.

## Self-guided players and gym programmes

- **Same hard rules.** Self-guided players are planned by the same solver (rest day, easy
  day before matches, growth-zone limits, ACWR cap, exam evenings off). Club training
  nights are a strong soft rule, so a red day or an exam still wins.
- **No coach, so only easier changes are automatic.** Re-plans have an RPE ceiling from
  the current plan, so applying them without approval can never add load. Each one shows
  as a why-card.
- **Safety flags without staff.** Pain or a red mood shows in-app advice to stop, tell a
  trusted adult and see a doctor or physio; the agents do not plan around it.
- **Consent under 16.** Sign-up needs a parent's email; the parent links with a one-time
  invite code and grants consent per data type. Before that, no check-ins, training logs
  or test results are stored.
- **Gym safety.** No jumps or heavy loads in the growth-spurt window; heavy lifts only
  after the growth spurt and from 16; recovery-only gym on red days; no eccentric work two
  days before a match. Covered by `tests/test_gym.py`.
- **Coach instructions** become weighted constraints, never overrides of the hard rules;
  notes mentioning pain or injury are refused and pointed to the physio.
- **Limits:** benchmarks and doses are placeholders; sign-up has no email verification or
  rate limiting yet.

## Dual registration and team sessions

- **H8** (hard): under-18s play at most 90 match minutes over two consecutive days across
  all their teams; `hard_violations` checks it and tests cover it.
- Only the **primary team's coach** approves changes; the second team's coach can see them.
- **Team sessions** from the training pitch never bypass the hard rules: each player gets
  the nearest safe version, and the reason is shown to the coach and the player.
- Match ratings are performance feedback, not selection decisions; they are labelled as a
  formula with placeholder weights.
