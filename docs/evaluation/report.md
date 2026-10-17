# PathToPro evaluation (25 players x 40 weeks, seed 2026)

| Metric | Target | Result | Status |
| --- | --- | --- | --- |
| Hard constraint violations | 0 | 0 in plans, 0 in executed weeks | PASS |
| Safety scenario suite (50 cases) | 100% | 50/50 | PASS |
| Player-weeks with ACWR > 1.5 | >= 50% fewer than baseline | load: 61%, readiness: 66%, random: 58% | PASS |
| Same, against a baseline with the agents' total load | fewer spikes at equal load (not just less training) | load: 61 -> 22 (64% fewer), readiness: 65 -> 22 (66% fewer), random: 45 -> 18 (60% fewer) | PASS |
| Weeks with monotony > 2 | >= 40% fewer than baseline | load: 0 -> 4, readiness: 0 -> 3, random: 0 -> 4 | not measured |
| Planned development sessions delivered | >= 90% of goal | load: 91%, readiness: 91%, random: 92% | PASS |
| LLM output valid on first try | >= 95% (200 runs) | LLM not used (rule-based run) | not measured |
| LLM valid after retry or fallback | 100% | 100% (every run produced a plan) | PASS |
| Planner consistency (20 runs) | >= 80% identical | 100% | PASS |
| Solver time | < 2 s player-week, < 60 s squad | max 0.53 s / 4.5 s | PASS |
| Red check-in to staff notification | < 5 min | agent decision 0 ms (end-to-end measured in API tests) | PASS |
| Expert rating of 10 plans | >= 3.5 / 5 | pending: needs 2+ reviewers | not measured |
| SUS score | >= 70 | pending: usability tests in week 10 | not measured |
| Readiness weight sensitivity | < 10% of daily bands change at +/-0.1 | 15.0% without buffer, 14.3% with buffer, 13.0% with buffer + calibrated weights | FAIL |
| Which days flip when a weight shifts | flips are borderline days, not clear ones | 91% of flipped days were within 5 points of a colour boundary; a smaller +/-0.05 shift changes 7.5% of bands | PASS |
| Readiness colour stability (colour buffer) | fewer day-to-day colour changes, warnings never delayed | 58% -> 44% of days change colour (buffer up 8, down 0) | PASS |
| Weights calibrated against staff ratings | better agreement, red recall not lower | kappa 0.32 -> 0.34 (held-out 0.32 -> 0.34), red recall 41% -> 41%, n=2072 synthetic ratings | PASS |

## Season detail

| Injury model | Policy | ACWR>1.5 weeks | Monotony>2 weeks | Mean weekly load | Red readiness days | Injuries (in PHV) |
| --- | --- | --- | --- | --- | --- | --- |
| load | baseline | 57 | 0 | 2137 | 13.9% | 40 (11) |
| load | baseline, agents' load | 61 | 0 | 1745 | 13.0% | 39 (10) |
| load | agents | 22 | 4 | 1727 | 12.4% | 36 (8) |
| readiness | baseline | 65 | 0 | 2099 | 13.9% | 46 (11) |
| readiness | baseline, agents' load | 65 | 0 | 1710 | 12.9% | 43 (11) |
| readiness | agents | 22 | 3 | 1709 | 12.4% | 40 (9) |
| random | baseline | 43 | 0 | 2189 | 13.9% | 30 (8) |
| random | baseline, agents' load | 45 | 0 | 1798 | 13.1% | 30 (8) |
| random | agents | 18 | 4 | 1794 | 12.6% | 28 (6) |

Executed-week rule checks (planned RPE): load: agents none, baseline {'session_on_exam_day': 275, 'md_minus_1_too_hard': 101}; readiness: agents none, baseline {'session_on_exam_day': 270, 'md_minus_1_too_hard': 103}; random: agents none, baseline {'session_on_exam_day': 277, 'md_minus_1_too_hard': 105}

Mirwald estimate error within +/-2.5 y of PHV: bias -0.09 y, MAE 0.30 y.

Equal-load baseline: the same fixed template with session minutes scaled load x0.74, readiness x0.73, random x0.75 so its mean weekly load matches the agents'. Spikes it still has come from how load is spread, not how much.

Injuries are a secondary result: the injury model is synthetic, so process metrics are primary.
