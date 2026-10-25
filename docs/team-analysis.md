# Team analysis: set pieces

The coach's **Team analysis** page shows how an opponent takes and defends set pieces:
where their corners go, who takes them, whether they produce shots, and where their
penalty and free-kick takers put the ball. It is built on real match events, not on the
synthetic academy season.

## Data

[StatsBomb Open Data](https://github.com/statsbomb/open-data), La Liga 2015/16: every one of
the 380 matches, all 20 teams. StatsBomb make it free "for research projects and genuine
interest in football analytics"; anyone who publishes analysis based on it must state the
source as StatsBomb and use their logo (from their media pack). The page credits the
source in its footer; the logo is not bundled yet (see Limits). Their licence is in the
open-data repository.

`python -m scouting.statsbomb` downloads each match's events and line-ups (~3.5 MB per
match), keeps only the set pieces and writes one compact file,
`backend/scouting/data/laliga_2015_16.json` (committed, so the app needs no network).
Pass another `--competition` / `--season` from StatsBomb's `competitions.json` to import
a different season; only seasons with full coverage give fair league comparisons (most
other La Liga seasons in the open data contain only Barcelona's matches).

## What is measured

Coordinates are StatsBomb's: a 120 x 80 yard pitch, every team attacking towards x = 120,
y = 0 on the attacking team's left. "Where it went" is the delivery's end point, which for
a cleared ball is where it was first touched.

| Measure | Definition |
| --- | --- |
| Corner side | Left or right corner flag, from the attacking team's view |
| Delivery zone | Measured from the corner's own touchline, so "near post" means the same thing from both flags. In the box: **near post** (up to 37 yards in, the near post is at 36), **far post** (43+ yards in, far post at 44), between the posts **six-yard box** (inside the six-yard line) or **penalty spot area**. Outside the box: **short** (within 25 yards of the flag) or **edge of the box** |
| Delivery | Inswinging, outswinging or straight, as recorded by StatsBomb |
| Corner ends in a shot | The same team shoots within 15 seconds of the corner, in the same possession |
| xG per corner | Sum of StatsBomb xG of those shots, per corner |
| Penalty / free-kick placement | Thirds of the goal mouth (left, centre, right) and height (low, middle, high) where the ball ended, **from the kicker's view**: the kicker's left is the goalkeeper's right. Only kicks on target count for placement, since a miss shows where the ball went, not where it was aimed |

## When a tendency is called out

Every share is shown with its count. A share is compared with the **rest of the league**
(the other 19 teams), and it is flagged ("More than the league" / "Less than the league")
and written into the scouting notes only when

- the team has at least 20 cases, and
- the 95% Wilson interval of the team's share does not contain the rest-of-league share.

That keeps a hot streak in eight corners from being reported as a habit. It is still a
screen, not proof: each team has about a dozen shares, so roughly one flag in twenty can
be chance. Penalties are too few per team (usually under ten) to be flagged at all; the
notes list each regular taker's kicks and say "small sample".

## Limits

- **One season, ten years old.** Squads and set-piece coaches change; the method carries
  over to newer data, the specific tendencies do not.
- **End point, not intention.** A near-post corner that is headed away at the near post
  and one aimed there look the same.
- **No body orientation or goalkeeper dive.** StatsBomb's open events don't say which way
  the goalkeeper went, so the page can't show "keeper dives early".
- **StatsBomb logo.** Their terms ask for the logo next to published analysis; add it
  from their media pack before the public website shows this page outside a coursework demo.
- **The academy's own matches have no event data.** The same functions would work on
  set-piece events logged for the club's matches; that logging doesn't exist yet.

Code: `backend/scouting/` (`statsbomb.py` import, `analysis.py` measures and notes),
`api/routers/analysis.py`, `frontend/src/coach/TeamAnalysis.tsx`. Tests:
`tests/test_scouting.py`.
