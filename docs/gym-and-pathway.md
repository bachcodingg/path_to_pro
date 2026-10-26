# Gym programmes and the self-guided pathway

## Gym programmes (`backend/gym/`, `config/gym.yaml`)

Every planned strength session turns into a concrete gym programme. It has two parts:

| Block | Who | What |
| --- | --- | --- |
| Warm-up | everyone | Mini-band walks, world's greatest stretch |
| Power | position | One explosive exercise for the position |
| Strength | everyone | A squat or deadlift pattern, a hinge, an upper-body pull or push |
| Position work | position | Two exercises for the position's demands |
| Injury prevention | everyone | Nordic hamstring curls and Copenhagen adductor planks (FIFA 11+ style) |
| Core, cool-down | everyone | Anti-rotation core, hip mobility |

Position emphasis:

| Position | Focus |
| --- | --- |
| Goalkeeper | Sideways push-off for diving, trunk for landing, shoulder stability |
| Centre-back | Duel strength, jumping for headers, neck strength, one-leg landings |
| Full-back | Repeated sprints, hamstring robustness, change of direction |
| Midfielder | Single-leg strength, anti-rotation core, strength-endurance |
| Winger | Acceleration and top speed, hamstrings and calves, 1v1 cuts |
| Striker | First step and jump, hip power for shooting, upper body to hold the ball up |

The same safety thinking as the planner applies to every programme:

- **Growth-spurt window (PHV):** no jumps and no heavy loads; technique doses only.
- **Before the growth spurt or under 14:** bodyweight and light loads, 2 x 10 for technique.
- **Heavy lifts** (trap-bar deadlift) only after the growth spurt, from 16, on a normal or better day.
- **Red readiness:** recovery gym only (isometric holds, core, mobility).
- **Amber readiness:** one set less, no jumps.
- **Match tomorrow:** short activation. **Match in two days:** no Nordic curls (next-day soreness), one set less.
- **Equipment:** self-guided players choose none / home / gym; exercises fall back to bodyweight alternatives.

Exercises rotate week to week, and the same inputs always give the same programme.
Coaches set an academy player's position on the scouting report; self-guided players set
their own. Doses are defaults for a coach to adjust, not a medical prescription.

## Self-guided pathway (`backend/pathway/`, `config/pathway.yaml`)

For players aged 13 and over who aren't in an academy. They sign up themselves, enter
their club's training nights and match day, and get a plan from the same CP-SAT planner
with the same hard rules (rest day, easy day before matches, growth-zone limits, ACWR cap).

| Level | Name | Sessions/week | Gym/week |
| --- | --- | --- | --- |
| 1 | Starter | 3 | 1 |
| 2 | Grassroots | 3 + match | 1 |
| 3 | Competitive amateur | 4 + match | 2 |
| 4 | Elite amateur | 5 + match | 2 |
| 5 | Trial-ready | 5 + match | 2 |

**Benchmarks:** six tests that need at most a phone, cones and a wall: 30 m sprint, Yo-Yo
IR1, standing long jump, juggling, wall passes in 30 s, weak-foot passing. Physical
targets are adjusted for age (13-17) and sex.

**Level-ups:** a player moves up one level when they meet the next level's benchmark in
at least 4 of 6 tests **and** logged at least 75% of the level's sessions over the last 4
weeks. Levels never go down automatically.

**The plan:** club nights become football sessions (a strong soft rule, so a red day or an
exam still wins). The level sets the weekly load and the number of gym sessions. The two
weakest tests become development goals, so the planner adds matching sessions and the
Today screen shows solo drills for them.

**No staff:** re-plans can only make a week easier, so they're applied automatically with
a why-card. Pain or a red mood shows safety advice in the app (stop, tell an adult, see a
doctor or physio), alerts a linked parent in the family view, and turns the next two days
into rest (pain, with 0 match minutes) or recovery (red mood).

**Under 16:** sign-up needs a parent's email. The player gets a one-time invite code; the
parent signs up with it and grants consent per data type. Until then the player gets
their plan and gym sessions, but no check-ins, logs or test results are stored.

## Coach instructions in plain words

On the scouting report a coach writes, for example, "keep him light until Thursday, no gym
this week". Claude (with a key) or a rule parser turns it into weight-9 planner
constraints. The coach sees the current and the new week side by side, then applies it.
The hard rules still apply, pain or injury notes are refused (they go to the physio), and
the change is logged in the match commentary and shown to the player as a why-card.

## Limitations

- Benchmarks, doses and level thresholds are placeholders for the demo, not validated norms.
- Self-guided load comes from what players log; with nothing logged for two weeks the
  planner assumes the level's normal week.
- Sign-up has no email verification or rate limiting yet.
