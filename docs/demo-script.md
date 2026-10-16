# Demo script (5 minutes)

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
   checkpoints and the 4-week goal. (Coach inbox also has "New development goal" cards.)

4. **Evidence (1 min)** - `docs/evaluation/report.md`: 0 hard-rule violations (baseline:
   ~375), 58-66% fewer ACWR spike weeks, 91% of goal sessions delivered, 50/50 safety
   scenarios, solver ≤ 0.21 s per player-week. SUS pending usability tests.

5. **Safety (30 s)** - sign in as any player, check in with mood "Not good". Sign in as
   **Physio** (`physio@demo.pathtopro`): the red check-in is in the queue within a second,
   with no agent reply to the player beyond "a staff member will talk to you".

Offline: the demo needs no API key; with `PATHTOPRO_LLM=off` everything is rule-based.
