"""Team analysis: opponents' set pieces, playing style, players and shots from public
event data (coach only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import CurrentUser, require
from domain.enums import Role
from scouting import analysis, style

router = APIRouter(prefix="/api/coach/analysis", tags=["analysis"])


def _found(value: dict | None) -> dict:
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not in the dataset")
    return value


@router.get("/teams")
def teams(user: CurrentUser = Depends(require(Role.COACH))):
    tables = {"table": style.standings(), "table_home": style.standings("home"), "table_away": style.standings("away")}
    return analysis.teams() | tables


@router.get("/teams/{team_id}")
def team(team_id: str, user: CurrentUser = Depends(require(Role.COACH))):
    """Set pieces: corners for and against, penalties, direct free kicks."""
    return _found(analysis.team_profile(team_id))


@router.get("/teams/{team_id}/style")
def team_style(team_id: str, user: CurrentUser = Depends(require(Role.COACH))):
    """Passing, shooting, duels, pressing and discipline against the rest of the league."""
    return _found(style.style_profile(team_id))


@router.get("/teams/{team_id}/players")
def team_players(team_id: str, user: CurrentUser = Depends(require(Role.COACH))):
    return _found(style.player_rows(team_id))


@router.get("/teams/{team_id}/shots")
def team_shots(team_id: str, user: CurrentUser = Depends(require(Role.COACH))):
    return _found(style.shot_map(team_id))
