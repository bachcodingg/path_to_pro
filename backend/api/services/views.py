"""Read models shared by the role views."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.rules import KPI_LABEL
from api.services import agent_runner
from domain.enums import ProposalStatus, SessionType
from domain.models import (
    Approval,
    DailyStatus,
    Player,
    Proposal,
    SessionLoad,
    StaffMember,
    WeeklyPlan,
    WellnessCheckin,
)
from planner.schema import PlanDay

SESSION_LABEL = {
    SessionType.REST: "Rest day",
    SessionType.RECOVERY: "Recovery",
    SessionType.TECHNICAL: "Technical",
    SessionType.TACTICAL: "Tactical",
    SessionType.STRENGTH: "Strength",
    SessionType.SPEED: "Speed",
    SessionType.MATCH: "Match",
}

FLAG_PLAYER_TEXT = {
    "load_spike": "Training load jumped",
    "high_monotony": "Every day felt the same",
    "short_sleep": "Short sleep",
    "low_hrv": "Body still recovering",
    "phv_window": "Growth zone",
    "readiness_red": "Low battery",
}

UNITS = {"sprint_10m": "s", "sprint_30m": "s", "cmj": "cm", "yoyo_ir1": "m"}


def day_json(d: PlanDay) -> dict:
    return {
        "date": d.date.isoformat(),
        "kind": d.kind.value,
        "label": SESSION_LABEL[d.kind],
        "rpe": d.rpe,
        "minutes": d.minutes,
        "load": d.rpe * d.minutes,
    }


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_days(db: Session, player: Player, start: date) -> list[dict]:
    return [day_json(d) for d in agent_runner.plan_days(db, player, start, 7)]


def status(db: Session, player_id: str, day: date) -> DailyStatus | None:
    return db.scalars(select(DailyStatus).where(DailyStatus.player_id == player_id, DailyStatus.day == day)).first()


def latest_status(db: Session, player_id: str, day: date) -> DailyStatus | None:
    return db.scalars(
        select(DailyStatus)
        .where(DailyStatus.player_id == player_id, DailyStatus.day <= day)
        .order_by(DailyStatus.day.desc())
        .limit(1)
    ).first()


def status_json(st: DailyStatus | None) -> dict | None:
    if st is None:
        return None
    return {
        "date": st.day.isoformat(),
        "score": st.readiness,
        "band": st.band,
        "acwr": st.acwr,
        "in_phv_window": st.in_phv_window,
        "maturity_offset": st.maturity_offset,
        "flags": st.flags,
        "chips": st.chips,
    }


def why_cards(db: Session, player: Player, limit: int = 5) -> list[dict]:
    """The most recent applied agent changes, with their data and who approved them."""
    out = []
    for p in db.scalars(
        select(Proposal)
        .where(
            Proposal.player_id == player.id,
            Proposal.status.in_([ProposalStatus.APPROVED, ProposalStatus.EDITED, ProposalStatus.AUTO_APPLIED]),
        )
        .order_by(Proposal.created_at.desc())
        .limit(limit)
    ):
        appr = db.scalars(select(Approval).where(Approval.proposal_id == p.id)).first()
        approver = db.get(StaffMember, appr.approver_id).name if appr else "Auto-applied (policy)"
        plan = db.get(WeeklyPlan, p.proposed_plan_id) if p.proposed_plan_id else None
        out.append(
            {
                "id": p.id,
                "kind": p.kind,
                "title": _card_title(p),
                "explanation": plan.explanation_player if plan else p.reason,
                "chips": p.data_chips,
                "approved_by": approver,
                "status": p.status.value,
                "changed_days": p.payload.get("changed_days", []),
                "created_at": p.created_at.isoformat(),
            }
        )
    return out


def _card_title(p: Proposal) -> str:
    return {
        "session_swap": "Your sessions were changed",
        "load_cut": "Your week was made lighter",
        "intensity_change": "Session intensity adjusted",
        "match_minutes": "Your match minutes are limited",
        "new_goal": "New development goal",
        "drill_suggestion": "New drills for you",
    }.get(p.kind, "Plan updated")


def daily_loads(db: Session, player_id: str, start: date, end: date) -> dict[date, float]:
    out = defaultdict(float)
    for sl in db.scalars(
        select(SessionLoad).where(SessionLoad.player_id == player_id, SessionLoad.day >= start, SessionLoad.day <= end)
    ):
        out[sl.day] += sl.load_au
    return out


def checkin_days(db: Session, player_id: str) -> list[date]:
    return sorted(c.day for c in db.scalars(select(WellnessCheckin).where(WellnessCheckin.player_id == player_id)))


def streak(days: list[date], today: date) -> int:
    s, d, have = 0, today, set(days)
    if d not in have:
        d -= timedelta(days=1)
    while d in have:
        s += 1
        d -= timedelta(days=1)
    return s


def badges(total_checkins: int, goals_met: int) -> list[dict]:
    """Badges are earned once and never taken away (missing a day never removes points)."""
    out = []
    for n, name in ((7, "First week"), (21, "Habit builder"), (50, "Iron routine"), (100, "Season pro")):
        out.append({"id": f"checkins_{n}", "name": name, "earned": total_checkins >= n, "rule": f"{n} check-ins"})
    out.append({"id": "goal_1", "name": "Goal getter", "earned": goals_met >= 1, "rule": "Meet a 4-week goal"})
    return out


def kpi_label(kpi: str) -> str:
    return KPI_LABEL.get(kpi, kpi)
