# Multi-seed evaluation (10 seeds, 25 players x 40 weeks)

Seeds 2026-2035. Each seed is a new squad, fixture list and noise draw; within a seed the three policies face the same world, so differences are paired. Values: mean [95% CI] over seeds.

- **baseline**: fixed weekly template with random RPE, blind to exams and fixtures (the plan's baseline).
- **heuristic**: the same template plus a coach's rules of thumb as if-statements: no session on exam days, easy day before and rest after a match, speed capped in the growth window, minutes cut 10-20% when ACWR is high, recovery on pain / red mood / red readiness. No solver, no LLM.
- **agents**: Monitor + CP-SAT planner + Coordinator, rule-based (no LLM).

## Load spikes (player-weeks with ACWR > 1.5)

| Injury model | Baseline | Heuristic | Agents | Agents vs baseline (% fewer) | Agents vs heuristic (% fewer) |
| --- | --- | --- | --- | --- | --- |
| load | 41 [34, 48] | 44 [37, 51] | 13 [8, 18] | 68 [56, 80] | 71 [60, 81] |
| readiness | 50 [42, 58] | 47 [37, 57] | 14 [11, 18] | 70 [59, 80] | 67 [57, 77] |
| random | 28 [21, 35] | 28 [20, 37] | 8 [4, 12] | 69 [51, 87] | 71 [57, 85] |

## Secondary: injuries, monotony, load, rule violations

| Injury model | Policy | Injuries | Monotony > 2 weeks | Mean weekly load (AU) | Executed rule violations |
| --- | --- | --- | --- | --- | --- |
| load | baseline | 30.5 [24.5, 36.5] | 0.0 [0.0, 0.0] | 2214 [2175, 2252] | 382 [355, 409] |
| load | heuristic | 28.4 [23.4, 33.4] | 0.0 [0.0, 0.0] | 1928 [1913, 1943] | 0 [0, 0] |
| load | agents | 27.9 [22.8, 33.0] | 1.1 [-0.4, 2.6] | 1821 [1768, 1875] | 0 [0, 0] |
| readiness | baseline | 35.9 [30.8, 41.0] | 0.0 [0.0, 0.0] | 2183 [2146, 2220] | 375 [350, 401] |
| readiness | heuristic | 29.7 [23.6, 35.8] | 0.0 [0.0, 0.0] | 1920 [1896, 1944] | 0 [0, 0] |
| readiness | agents | 31.9 [27.2, 36.6] | 0.9 [-0.5, 2.3] | 1787 [1744, 1831] | 0 [0, 0] |
| random | baseline | 19.6 [14.5, 24.7] | 0.0 [0.0, 0.0] | 2271 [2234, 2307] | 393 [365, 421] |
| random | heuristic | 17.8 [12.8, 22.8] | 0.0 [0.0, 0.0] | 1978 [1956, 2000] | 0 [0, 0] |
| random | agents | 19.0 [14.2, 23.8] | 1.1 [-0.4, 2.6] | 1899 [1851, 1948] | 0 [0, 0] |

## Paired differences, agents minus reference (negative = agents lower)

| Injury model | Injuries vs baseline | Injuries vs heuristic | Monotony weeks vs baseline | Monotony weeks vs heuristic |
| --- | --- | --- | --- | --- |
| load | -2.6 [-5.7, 0.5] | -0.5 [-3.7, 2.7] | 1.1 [-0.4, 2.6] | 1.1 [-0.4, 2.6] |
| readiness | -4.0 [-6.0, -2.0] | 2.2 [-0.1, 4.5] | 0.9 [-0.5, 2.3] | 0.9 [-0.5, 2.3] |
| random | -0.6 [-3.0, 1.8] | 1.2 [-1.2, 3.6] | 1.1 [-0.4, 2.6] | 1.1 [-0.4, 2.6] |

A confidence interval that contains 0 means the difference is not distinguishable from seed-to-seed noise. Injuries come from a synthetic injury model, so they are a secondary result; and the agents' planner penalises projected ACWR directly, so fewer ACWR spikes is partly the objective being met, not independent evidence of benefit.
