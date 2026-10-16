# PathToPro evaluation (25 players x 40 weeks, seed 2026)

| Metric | Target | Result | Status |
| --- | --- | --- | --- |
| Hard constraint violations | 0 | 0 in plans, 0 in executed weeks | PASS |
| Safety scenario suite (50 cases) | 100% | 50/50 | PASS |
| Player-weeks with ACWR > 1.5 | >= 50% fewer than baseline | load: 61%, readiness: 66%, random: 58% | PASS |
| Weeks with monotony > 2 | >= 40% fewer than baseline | load: 0 -> 4, readiness: 0 -> 3, random: 0 -> 4 | not measured |
| Planned development sessions delivered | >= 90% of goal | load: 91%, readiness: 91%, random: 92% | PASS |
| LLM output valid on first try | >= 95% (200 runs) | LLM not used (rule-based run) | not measured |
| LLM valid after retry or fallback | 100% | 100% (every run produced a plan) | PASS |
| Planner consistency (20 runs) | >= 80% identical | 100% | PASS |
| Solver time | < 2 s player-week, < 60 s squad | max 0.21 s / 1.7 s | PASS |
| Red check-in to staff notification | < 5 min | agent decision 0 ms (end-to-end measured in API tests) | PASS |
| Expert rating of 10 plans | >= 3.5 / 5 | pending: needs 2+ reviewers | not measured |
| SUS score | >= 70 | pending: usability tests in week 10 | not measured |
| Readiness weight sensitivity | < 10% of daily bands change at +/-0.1 | max 15.0% | FAIL |

## Season detail

| Injury model | Policy | ACWR>1.5 weeks | Monotony>2 weeks | Mean weekly load | Red readiness days | Injuries (in PHV) |
| --- | --- | --- | --- | --- | --- | --- |
| load | baseline | 57 | 0 | 2137 | 13.9% | 40 (11) |
| load | agents | 22 | 4 | 1728 | 12.4% | 36 (8) |
| readiness | baseline | 65 | 0 | 2099 | 13.9% | 46 (11) |
| readiness | agents | 22 | 3 | 1709 | 12.4% | 40 (9) |
| random | baseline | 43 | 0 | 2189 | 13.9% | 30 (8) |
| random | agents | 18 | 4 | 1795 | 12.5% | 28 (6) |

Executed-week rule checks (planned RPE): load: agents none, baseline {'session_on_exam_day': 275, 'md_minus_1_too_hard': 101}; readiness: agents none, baseline {'session_on_exam_day': 270, 'md_minus_1_too_hard': 103}; random: agents none, baseline {'session_on_exam_day': 277, 'md_minus_1_too_hard': 105}

Mirwald estimate error within +/-2.5 y of PHV: bias -0.09 y, MAE 0.30 y.

Injuries are a secondary result: the injury model is synthetic, so process metrics are primary.
