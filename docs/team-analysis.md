# Pro league analysis

Pro league analysis is a separate app, **Pro League Data Tracking** (`/leagues/`), built
on the same platform as PathToPro: one account, one API and one design system, but its own
entry page (`frontend/leagues/index.html`, `frontend/src/leagues/`), name, icon, colours and
install manifest. A PathToPro account signs in to it, and it is open to every kind of
account: it is public match data with nothing about our players in it. PathToPro links to it
from the staff column and the player sidebar; old `/pro/...` addresses open it. Coaches use it to study an opponent's style; players to see how the pros in their
position play. It shows how a team passes, where they shoot from, how they do in the air,
how hard they press, how they take and defend set pieces, and which players do what, plus
every result with a match centre. It is built on real match events, not on the synthetic
academy season.

| Competition | What the open data has | What the section shows |
| --- | --- | --- |
| La Liga 2015/16 | all 380 matches | every team, ranked against the rest of the league; table; results |
| Premier League 2015/16 | all 380 matches (Leicester City's title) | the same |
| Ligue 1 2015/16 | 377 of 380 (three missing, so a few teams have 37) | the same |
| Bundesliga 2023/24 | Bayer Leverkusen's 34 matches only (the unbeaten season) | Leverkusen against their opponents in those matches, no ranks and no table; results |
| Ligue 1 2021/22 and 2022/23 | Paris Saint-Germain's 58 league matches only (26 and 32) | PSG against their opponents, no ranks and no table; Mbappé, Messi and Neymar's player pages |
| Champions League | the final of 14 seasons, 2004-2019 | the finals with a match centre each; no team comparison from one match a year |

A team's page (`/leagues/<competition>/teams/<team>`):

| Tab | What it shows |
| --- | --- |
| Overview | League position and record, **strengths**, **weaknesses** and **how they play** (only measures that clearly differ from the league), ten key numbers, the league table |
| Attack | Shot map (their shots or shots conceded; foot or header; open play, counter, set play, penalty) with tap-in / box / long-shot totals, and every shooting measure |
| Passing | Accuracy of short, medium and long passes, long-ball share, crosses, through balls, passes into the final third and the box, key passes, switches, goal kicks played long |
| Duels & headers | Aerial duels won, dribbles completed, tackles won |
| Defending | Pressing (PPDA, pressures, counter-pressing, high recoveries), shots and xG conceded, how far out opponents are kept, discipline |
| Set pieces | Corners (delivery map, zones, swing, takers), corners defended, penalties and direct free kicks (goal-mouth map, placement by kicker) |
| Players | Squad leaders (goals, assists, key passes, aerial duels won, tackles + interceptions), then the squad, sortable, in four views: shooting (tap-ins, headers, long shots, xG, conversion), passing (accuracy by length, key passes, assists), duels (aerial %, dribbles), defending (tackles + interceptions, pressures, cards) |
| Table | The league table as on laliga.com: Pl, W, D, L, GF, GA, GD, Pts and the last five results; all matches, home only or away only; the 2015/16 Champions League (1-4), Europa League (5-6) and relegation (18-20) places |

Pick a second team under **Compare with** to see it next to the first: as a hollow ring
on every bar and as "vs" numbers.

The page is laid out like a league website's club page: a strip of every club's badge to
switch team, then a header in the club's colour with its position, points, record and form.
The badges are drawn from the clubs' colours with LaLiga's three-letter codes, not from the
clubs' crests, which are their trademarks.

## Data

[StatsBomb Open Data](https://github.com/statsbomb/open-data); the competitions and their
StatsBomb ids are in `backend/scouting/competitions.py`. StatsBomb make it free "for research projects and genuine
interest in football analytics"; anyone who publishes analysis based on it must state the
source as StatsBomb and use their logo (from their media pack). The page credits the
source in its footer; the logo is not bundled yet (see Limits). Their licence is in the
open-data repository.

`python -m scouting.statsbomb --all` (or one key, e.g. `premier-league`) downloads each match's events and line-ups (~3.5 MB per
match, cached gzipped so a change of definition re-runs offline) and writes two compact
files, committed so the app needs no network:

- `backend/scouting/data/<file>.json`: corners, penalties and direct free kicks (La Liga: 3,841 / 97 / 409)
- `backend/scouting/data/<file>_play.json`: team-match rows of counts with the date and matchday, players' season counts with minutes, every shot (La Liga: 760 / 547 / 9,168)

Team names in the events are matched to the match list by team id (some Ligue 1 files say
"Marseille" in the events and "Olympique Marseille" in the match), and penalty shoot-out
goals are kept apart from match play.

Pass another `--competition` / `--season` from StatsBomb's `competitions.json` to import
a different season; only seasons with full coverage give fair league comparisons (most
other La Liga seasons in the open data contain only Barcelona's matches).

**Checks that the import is complete and right** (in `tests/test_scouting_play.py` and
by hand): the La Liga table rebuilt from the 380 scores is the real 2015/16 table
(Barcelona 91, Real Madrid 90, Atlético 88 points); Cristiano Ronaldo has 35 league goals,
Benzema 24 and Bale 19, as in the official records; Atlético conceded 18. Premier League:
Leicester 81, Arsenal 71, Tottenham 70; Kane 25 goals, Vardy and Agüero 24. Ligue 1: PSG
first (93 points from their 37 matches in the data; 96 from 38 in reality). Leverkusen:
W28 D6 L0, goals 89-24. The 14 finals have the real scores and shoot-outs (Liverpool 3-2
on penalties in 2005, Chelsea 4-3 in 2012, Real Madrid 5-3 in 2016).

## Definitions

Coordinates are StatsBomb's: a 120 x 80 yard pitch, every team attacking towards x = 120,
y = 0 on the attacking team's left. Code: `backend/scouting/play.py`.

| Measure | Definition |
| --- | --- |
| Open-play pass | Any pass except corners, free kicks, throw-ins, goal kicks and kick-offs. Passes recorded as "Unknown" or "Injury clearance" are not attempts. Complete when StatsBomb records no outcome |
| Short / medium / long | Under 15 yards / 15-35 / 35 yards or more (32 m, the usual "long ball") |
| Final-third and box entries | A completed pass that starts before x = 80 and ends beyond it; one that starts outside the penalty area and ends inside it |
| Key pass | A pass followed directly by a shot (StatsBomb's shot or goal assist) |
| Share of the match's passes | Stand-in for possession: StatsBomb's open events have no possession clock |
| Shot zones | **Tap-in range**: inside the six-yard box. **Rest of the box**. **Long shot**: outside the box. Penalties are left out of zone, conversion and xG-per-shot measures |
| Big chance | A non-penalty shot with StatsBomb xG of 0.3 or more |
| Shots from counters / set plays | StatsBomb's play pattern of the possession: "From Counter"; "From Corner", "From Free Kick", "From Throw In" |
| Aerial duel | Won: StatsBomb's `aerial_won` on a pass, shot, clearance or miscontrol. Lost: a duel of type "Aerial Lost" |
| PPDA | The opponent's open-play passes in their own 60% of the pitch, per tackle, interception or foul by this team in that area. Lower means more pressing |
| High pressure / recovery | In the attacking third (x of 80 or more) |
| Counter-pressure | A pressure StatsBomb marks as within 5 seconds of losing the ball |
| Corner zones | Measured from the corner's own touchline, so "near post" means the same from both flags. In the box: **near post** (up to 37 yards in, the near post is at 36), **far post** (43+ yards in, far post at 44), between the posts **six-yard box** or **penalty spot area**. Outside: **short** (within 25 yards of the flag) or **edge of the box** |
| Corner ends in a shot | The same team shoots within 15 seconds of the corner, in the same possession |
| Penalty / free-kick placement | Thirds of the goal mouth where the ball ended, **from the kicker's view** (the kicker's left is the goalkeeper's right). Only kicks on target count, since a miss shows where the ball went, not where it was aimed |
| Form | The last five league results in date order (the import keeps each match's date and matchday) |
| Home / away table | Only the 19 home or 19 away matches; home and away points add up to the full table |
| Player minutes | Starters from 0, substitutes from their entry, a red card ends a player's match. Per-90 rates need 450 minutes, accuracies a minimum number of attempts |

## When something is called a strength, weakness or habit

Every number is shown with the rest of the league (the other 19 teams) and a rank.

- **Team style measures** (`scouting/style.py`): a share is pooled over the season (all
  completed long passes / all long passes), a rate is a per-match mean. The 95% interval
  comes from **match-to-match variation** (t distribution over the team's 38 matches),
  not from the number of passes, because passes within a match are not independent. A
  measure gets a label only when that interval excludes the league value: **strength** or
  **weakness** when more is clearly better or worse (pass accuracy, goals conceded),
  **habit** when it is a matter of style (long-ball share, pressures).
- **Set-piece shares** (`scouting/analysis.py`): at least 20 cases and a 95% Wilson
  interval that excludes the league share. Penalties are too few per team to be flagged;
  the notes list each taker's kicks and say "small sample".

It is a screen, not proof: with about 60 measures per team, two or three labels can be
chance. The bars on each measure show where the team sits between the league's lowest
and highest team, so a label can always be checked against the spread.

## Players

The **Players** tab of the Pro League app (`/leagues/players`) analyses players from two
sources.

| | Match events (StatsBomb Open Data) | 2024/25 season (API-Football) |
| --- | --- | --- |
| What it is | Every event of the matches in the free data | League season totals per player |
| Seasons | La Liga, Premier League, Ligue 1 2015/16; PSG's league matches 2021/22 and 2022/23 (Mbappé, Messi, Neymar); Leverkusen 2023/24 | 2024/25: Premier League, La Liga, Ligue 1, Bundesliga, Serie A |
| Full squads | Real Madrid, Barcelona, PSG (2015/16 and 2021-23), Manchester City, Manchester United, Chelsea, Liverpool, Arsenal | The same nine clubs, Bayern included |
| A player's page | Totals, per-90 rates, percentiles, every shot on a pitch map | Totals, per-90 rates, rating, percentiles |
| Needs | Nothing: the data is committed | An API-Football key, imported once on the server |

- **Bayern Munich** have no league season in the free event data (only their matches
  against Leverkusen), so their squad is in the 2024/25 numbers only.
- **Best of the rest**: one player for every other club, the most goals plus assists among
  players with 900+ minutes (more minutes break a tie). A plain rule anyone can check; it
  favours attackers.
- **Percentiles** compare a player's per-90 numbers with the regulars (900+ minutes) in
  the same position group: in that league for the event data, across the five leagues for
  2024/25. Ties count half and the player is part of his own group, so 50 is the middle. A
  club season (one club's matches only) has no fair group, so its pages show the numbers
  without percentiles. Per-90 rates start at 450 minutes.
- **The 2024/25 import** (`python -m scouting.apifootball`, with `APIFOOTBALL_KEY` set):
  API-Football's free plan allows 100 requests a day and seasons from two to four years
  back, so 2024/25 is the newest it gives (the current season needs a paid plan). It also
  reads only the first 3 pages of any list, so a whole league (50+ pages) is out of reach.
  The script therefore reads each club's own players (2-3 pages), the featured clubs first:
  about 225 requests for the five leagues, so three days. A few big clubs list more than 60
  players (youth and departed players included), so their fourth page is out of reach; the
  data file names them (`lists_cut_after_3_pages`). For Real Madrid every player with league
  minutes was in the first three. It caches every page and carries
  on the next day; until every club is in, the page says how many are.
  It keeps numbers only, never the API's player photos or club logos. Its output,
  `backend/scouting/data/season_2024_25.json`, is in `.gitignore`: check API-Football's
  terms before publishing it. Without it, the app says the season is not imported.

## Club crests

A club's real crest is shown only where it is free to reuse
(`frontend/src/shared/crests.ts`, files in `frontend/public/crests/`): public domain on
Wikimedia Commons (mostly simple text logos, such as Bayern, Dortmund, Juventus, Inter and
AC Milan), public domain in the US where the site is hosted (Barcelona, PSG, Bordeaux,
Eibar), or CC BY-SA (Köln). They stay trademarks of their clubs. Real Madrid, the English
clubs and the rest are copyrighted, so they keep a badge drawn from their colours. The Pro
League home page lists every crest with its licence and source.

## Limits

- **Mostly one season, ten years old.** Squads and coaches change; the method carries
  over to newer data, the specific tendencies do not. Newer seasons in the open data
  (Bundesliga 2023/24) cover one club only.
- **No match-to-match variation, no label.** A measure that is the same in every match
  (Leverkusen had no red card) has no interval, so it is never called a strength.
- **Possession is approximated** by the share of passes; xG is StatsBomb's model.
- **End point, not intention.** A corner headed away at the near post and one aimed there
  look the same; a blocked shot's location is where it was struck.
- **No goalkeeper dive direction** in the open events, so no "keeper dives early".
- **StatsBomb logo.** Their terms ask for the logo next to published analysis; add it
  from their media pack before the public website shows this page outside a coursework demo.
- **The academy's own matches have no event data.** The same functions would work on
  events logged for the club's matches; that logging doesn't exist yet.

Code: `backend/scouting/` (`statsbomb.py` import, `play.py` open-play counts,
`analysis.py` set pieces, `style.py` team measures, players and shots, `players.py` player
profiles, `apifootball.py` and `season.py` the 2024/25 season),
`api/routers/analysis.py`, `frontend/src/coach/analysis/`. Tests:
`tests/test_scouting.py`, `tests/test_scouting_play.py`, `tests/test_scouting_players.py`.
