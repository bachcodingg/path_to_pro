"""Pro league analysis: real top-flight matches from public event data (StatsBomb Open
Data). Open to every signed-in user: it is public data and holds nothing about our players.

Per competition (scouting.competitions): teams, the table, a team's playing style, set
pieces, players and shots, and every match with a match centre."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import CurrentUser, current_user
from scouting import analysis, style
from scouting.competitions import COMPETITIONS, Competition

router = APIRouter(prefix="/api/pro", tags=["pro leagues"])


def _comp(comp: str) -> Competition:
    c = COMPETITIONS.get(comp)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Competition not in the dataset")
    return c


def _found(value: dict | None) -> dict:
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not in the dataset")
    return value


@router.get("/competitions")
def competitions(user: CurrentUser = Depends(current_user)):
    out = []
    for c in COMPETITIONS.values():
        t = analysis.teams(c.key)
        out.append(c.to_json() | {"matches": t["matches"], "teams": len(t["teams"])})
    return out


@router.get("/{comp}/teams")
def teams(comp: str, user: CurrentUser = Depends(current_user)):
    c = _comp(comp)
    out = analysis.teams(c.key) | {"competition": c.to_json()}
    if c.coverage == "league":
        out |= {
            "table": style.standings(comp=c.key),
            "table_home": style.standings("home", c.key),
            "table_away": style.standings("away", c.key),
        }
    return out


@router.get("/{comp}/teams/{team_id}")
def team(comp: str, team_id: str, user: CurrentUser = Depends(current_user)):
    """Set pieces: corners for and against, penalties, direct free kicks."""
    return _found(analysis.team_profile(team_id, _comp(comp).key))


@router.get("/{comp}/teams/{team_id}/style")
def team_style(comp: str, team_id: str, user: CurrentUser = Depends(current_user)):
    """Passing, shooting, duels, pressing and discipline against the rest of the league."""
    return _found(style.style_profile(team_id, _comp(comp).key))


@router.get("/{comp}/teams/{team_id}/players")
def team_players(comp: str, team_id: str, user: CurrentUser = Depends(current_user)):
    return _found(style.player_rows(team_id, _comp(comp).key))


@router.get("/{comp}/teams/{team_id}/shots")
def team_shots(comp: str, team_id: str, user: CurrentUser = Depends(current_user)):
    return _found(style.shot_map(team_id, _comp(comp).key))


@router.get("/{comp}/matches")
def matches(comp: str, user: CurrentUser = Depends(current_user)):
    c = _comp(comp)
    return {"competition": c.to_json(), "matches": style.matches(c.key)}


@router.get("/{comp}/matches/{match_id}")
def match(comp: str, match_id: int, user: CurrentUser = Depends(current_user)):
    report = style.match_report(match_id, _comp(comp).key)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match not in the dataset")
    return report
