# Teams, careers and match ratings

## Dual registration (`domain.Registration`, planner rule H8)

Young players often play for two teams: their age group and the club's men's or reserve
team. PathToPro registers the player with every team and puts all fixtures into **one**
plan.

- **H8 (hard rule, under 18):** at most 90 match minutes over two consecutive days. The
  planner chooses the minutes (0, 30, 45, 60 or 90 per match). The primary team's match
  keeps its minutes first; the second match takes what is left. The player's why-card
  explains it, and My week shows "Match 0'" with the reason.
- **Two coaches, one inbox.** The second team's coach sees the player on the heatmap and in
  the inbox (with a "Dual registration" chip), but only the primary team's coach approves.
- **Two matches on the same day:** the primary team's match counts.

Demo: `dual@demo.pathtopro` plays for the academy (Saturday) and PathToPro FC Men in the
Kakkonen (Sunday). `mencoach@demo.pathtopro` is the men's team coach.

## League ladder (`config/competitions.yaml`)

Each competition has a country, a category (adult, youth, reserve), a tier and a `level`
(0-100) on one scale across men's and youth football. The Finnish structure is the first
example: Veikkausliiga, Ykkösliiga, Ykkönen, Kakkonen, Kolmonen and lower tiers, reserve
teams, and national and regional U15/U17/U19 leagues. The levels are placeholder
judgements; add a country by adding entries.

**Exposure** weights minutes by level ("full matches at the top level"), so 90 minutes in
the men's fourth tier count for more than 90 in a regional youth league.

## Career (player app, "Career" tab)

- Teams the player is registered with this season.
- Season card: average rating, appearances, minutes, goals, assists, exposure; split by competition.
- Rating trend chart and recent matches; tap a match for its rating breakdown and the player's own rating.
- **My pathway:** the highest league level per season, as a step chart.
- Past seasons table; players can add earlier seasons.

## Match diary

After a match (any of the player's teams, from the last 7 days), the player fills in
minutes, position, goals, assists, a 1-10 self-rating and how hard it was. It:

- feeds the career stats (coach stats win when both exist),
- adds the match load (effort x minutes) to the load history, so the planner sees the real
  minutes instead of assuming 90,
- shows the self-rating next to the coach's rating.

## Match ratings (`backend/performance/rating.py`, coach "Match ratings")

A 3.0-10.0 rating per player per match, inspired by rating apps but with our own
transparent formula: base 6.3 plus position-weighted contributions (goals, assists, shots
on target, key passes, pass accuracy over volume, dribbles, tackles, interceptions, duels,
saves, goals conceded, clean sheets, errors leading to goals, cards, team result). Every
rating has its breakdown, e.g. "Goals +1.0, Pass accuracy 91% +0.33, Goals conceded x2
-0.30". Under 10 minutes there is no rating.

Colours: 8.0+ blue (outstanding), 7.0-7.9 green, 6.5-6.9 light green, 6.0-6.4 orange, below 6 red.

Coaches enter stats per match on a stat sheet (or a data provider fills them later through
the same endpoint: `PUT /api/coach/matches/{id}/ratings`). Without coach stats, the match
diary gives an estimate (shown in italics). The weights are defaults to tune with staff,
like the readiness weights.

### Line-up view

Each match opens on a **Line-up** tab: the starting XI on the pitch in the formation read
from their positions (e.g. 4-3-3, 4-2-4), each player with their rating badge, goals (ball),
assists (A) and the minute they came off; a star marks the player of the match. Next to it:
the team rating (average), the substitutes who came on (with their minutes and ratings),
and the players who didn't play. Tap any player for their rating breakdown. The **Stat
sheet** tab is where coaches enter or correct the stats.

### Rating progress

Every rated match in date order, labelled by month and match number ("Sep M1", "Sep M2",
"Oct M1", ...), with:

- dots coloured by rating,
- the average of the last 5 matches (green line),
- a straight-line trend over all matches (dashed orange), with "+0.31 per 10 matches",
  last 5 vs first 5, and a verdict: improving (+0.15 or more per 10 matches), steady or dipping.

Players see it on their Career tab; coaches see it on the player's scouting report.

## Training pitch (coach)

The squad's week on one board. The coach drags a team session (technical, tactical, gym,
speed, recovery, with an effort level) onto a day, or picks it and presses "Place". Every
player is checked against the hard rules: anyone for whom it isn't safe (day before a
match, growth zone, exam, load cap, rest day, red battery today) gets the nearest safe
version (lower effort, then recovery, then rest) with the reason on the cell. Preview,
then "Apply to squad": each player's week updates, the change is logged, and players get
a why-card ("Your coach planned a team speed session on Friday. For you it's recovery at
effort 3 because: day before a match").

## Limitations

- Demo match stats are synthetic. Competition levels and rating weights are placeholders.
- No data-provider integration yet (the ratings endpoint accepts the stats).
