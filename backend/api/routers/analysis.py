"""Team analysis: opponents' set-piece tendencies from public event data (coach only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import CurrentUser, require
from domain.enums import Role
from scouting import analysis

router = APIRouter(prefix="/api/coach/analysis", tags=["analysis"])


@router.get("/teams")
def teams(user: CurrentUser = Depends(require(Role.COACH))):
    return analysis.teams()


@router.get("/teams/{team_id}")
def team(team_id: str, user: CurrentUser = Depends(require(Role.COACH))):
    profile = analysis.team_profile(team_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not in the dataset")
    return profile
