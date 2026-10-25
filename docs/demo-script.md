# Demo script (7 minutes)

Setup: `docker compose up --build`, open http://localhost:8080. The seeder resets the
synthetic season and sets "today" to Thursday of week 12. All passwords: `demo1234`.

1. **Problem (30 s)** - one slide: load spikes, growth spurts, poor sleep, no
   development plan, mental pressure.

2. **Prevention flow (2 min)**
   - Phone (or narrow window): sign in as **Leon U.** (`p15@demo.pathtopro`). Do the
     morning check-in: 4 cards + mood, under 30 seconds.
   - Desktop: sign in as **Coach** (`coach@demo.pathtopro`). The Dressing room heatmap
     shows Leon's red cells, a growth-zone ring and a load-spike triangle.
   - Substitution board: Leon's card shows the current week vs the proposed week,
     with chips "Sleep 5.5 h x 3", "Load +61%", "HRV -2.1 SD", "Growth zone". Press **A**.
   - Back on the phone: Today shows the updated session; the "Why?" card explains the
     change and says "Approved by Alex Weber".

3. **Development flow (1 min)** - Leon's card: attributes as bio-banded percentiles; tap
   jump power for the test history and the linked drills. Road to Pro shows the test-day
   checkpoints and the 4-week goal. The **Gym** tab shows his position's session: the
   shared injury-prevention work plus his position block, with growth-zone limits on top.
   Coach view: on a player's scouting report, type "keep him light until tomorrow, no gym
   this week", press Preview, then Apply.

4. **Beyond the academy (1 min)** - sign in as **Self-guided player** (`amateur@demo.pathtopro`):
   Maya, 17, plays for her local club. Today shows level 2 "Grassroots" and her week
   built around club training (Tue, Thu) and Saturday matches. Open **Levels**, pick "Wall
   passes in 30 s", log 19: she meets 4 of 6 benchmarks and moves up to level 3. Anyone
   can sign up at `/register`; under-16s get a parent invite code.

5. **Two teams, one plan (1 min)** - sign in as **Player (U19 + men's team)**: My week shows
   the U19 match on Saturday at 90 minutes and the men's Kakkonen match on Sunday at 0' (rule
   H8: under-18s play at most 90 minutes over back-to-back days). **Career** shows both
   teams, ratings and the pathway chart; fill in the match diary. As **Coach**: Training
   pitch, drag "Speed" onto Friday: every player gets an easier version (day before a match),
   apply. Match ratings: open the last match, expand a rating to see its breakdown.

6. **Evidence (1 min)** - `docs/evaluation/seeds.md` (10 seeds, 95% CIs): 0 hard-rule
   violations, 68-70% fewer ACWR spike weeks than the plan's baseline and still 67-71% fewer
   than a heuristic coach that follows the same rules as if-statements, 54/54 safety
   scenarios. Say the limits out loud: no detectable injury difference vs the heuristic, the
   agents add ~1 high-monotony week per season, the LLM and SUS are not measured yet.

7. **Safety (30 s)** - sign in as any player, check in with mood "Not good". Sign in as
   **Physio** (`physio@demo.pathtopro`): the red check-in is in the queue within a second,
   with no agent reply to the player beyond "a staff member will talk to you".

Offline: the demo needs no API key; with `PATHTOPRO_LLM=off` everything is rule-based.
