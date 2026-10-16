"""Data model (plan section 6): 22 entities on PostgreSQL via SQLAlchemy 2.

Columns holding health data carry `info={"health": True}`. The API layer uses
this tag for field-level encryption and to write an AuditLog entry on every read.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from domain.enums import AgentName, ConsentDataType, ProposalStatus, Role, SessionType

HEALTH = {"health": True}


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


def health_columns() -> dict[str, list[str]]:
    """Table -> health-tagged columns, for encryption and audit."""
    out: dict[str, list[str]] = {}
    for table in Base.metadata.sorted_tables:
        cols = [c.name for c in table.columns if c.info.get("health")]
        if cols:
            out[table.name] = cols
    return out


# --------------------------------------------------------------------------- people

player_guardians = Table(
    "player_guardians",
    Base.metadata,
    Column("player_id", ForeignKey("players.id", ondelete="CASCADE"), primary_key=True),
    Column("guardian_id", ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True),
)


class Squad(Base):
    __tablename__ = "squads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(100))
    age_group: Mapped[str] = mapped_column(String(10))  # e.g. U15
    players: Mapped[list[Player]] = relationship(back_populates="squad")


class StaffMember(Base):
    __tablename__ = "staff_members"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    role: Mapped[Role] = mapped_column(Enum(Role))
    squad_id: Mapped[str | None] = mapped_column(ForeignKey("squads.id"))


class Player(Base):
    __tablename__ = "players"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    squad_id: Mapped[str] = mapped_column(ForeignKey("squads.id"))
    display_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(200), unique=True)
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(10))
    preferred_days: Mapped[list[int]] = mapped_column(JSON, default=list)
    # Named adult who receives red check-ins and pain reports (no agent counselling).
    escalation_contact_id: Mapped[str | None] = mapped_column(ForeignKey("staff_members.id"))
    squad: Mapped[Squad] = relationship(back_populates="players")
    guardians: Mapped[list[Guardian]] = relationship(secondary=player_guardians, back_populates="players")


class Guardian(Base):
    __tablename__ = "guardians"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    players: Mapped[list[Player]] = relationship(secondary=player_guardians, back_populates="guardians")


class ConsentRecord(Base):
    """Per data type, revocable. The latest row per (player, data_type) wins."""

    __tablename__ = "consent_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    guardian_id: Mapped[str | None] = mapped_column(ForeignKey("guardians.id"))
    data_type: Mapped[ConsentDataType] = mapped_column(Enum(ConsentDataType))
    granted: Mapped[bool] = mapped_column(Boolean)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# --------------------------------------------------------------------------- schedule and load


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    squad_id: Mapped[str] = mapped_column(ForeignKey("squads.id"), index=True)
    kickoff: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    opponent: Mapped[str] = mapped_column(String(100))
    competition: Mapped[str | None] = mapped_column(String(100))
    is_evening: Mapped[bool] = mapped_column(Boolean, default=False)


class Session(Base):
    """A scheduled training session for a squad, or for one player if player_id is set."""

    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    squad_id: Mapped[str | None] = mapped_column(ForeignKey("squads.id"), index=True)
    player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[SessionType] = mapped_column(Enum(SessionType))
    planned_rpe: Mapped[float | None] = mapped_column(Float)
    planned_minutes: Mapped[int | None] = mapped_column(Integer)


class SessionLoad(Base):
    """What a player actually did: sRPE = RPE x minutes."""

    __tablename__ = "session_loads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"))
    match_id: Mapped[str | None] = mapped_column(ForeignKey("matches.id"))
    day: Mapped[date] = mapped_column(Date, index=True)
    rpe: Mapped[float] = mapped_column(Float, info=HEALTH)
    minutes: Mapped[float] = mapped_column(Float)
    load_au: Mapped[float] = mapped_column(Float, info=HEALTH)


# --------------------------------------------------------------------------- wellness and growth


class WellnessCheckin(Base):
    __tablename__ = "wellness_checkins"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    sleep_quality: Mapped[int] = mapped_column(Integer, info=HEALTH)  # Hooper items 1-7
    fatigue: Mapped[int] = mapped_column(Integer, info=HEALTH)
    stress: Mapped[int] = mapped_column(Integer, info=HEALTH)
    soreness: Mapped[int] = mapped_column(Integer, info=HEALTH)
    mood_red: Mapped[bool] = mapped_column(Boolean, default=False, info=HEALTH)
    pain_reported: Mapped[bool] = mapped_column(Boolean, default=False, info=HEALTH)
    # No free-text diary in the MVP (data minimisation).
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    duration_s: Mapped[float | None] = mapped_column(Float)  # UI target: median < 30 s


class SleepRecord(Base):
    __tablename__ = "sleep_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    night_of: Mapped[date] = mapped_column(Date, index=True)
    hours: Mapped[float] = mapped_column(Float, info=HEALTH)
    source: Mapped[str] = mapped_column(String(30), default="manual")


class HRVRecord(Base):
    __tablename__ = "hrv_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    ln_rmssd: Mapped[float] = mapped_column(Float, info=HEALTH)
    source: Mapped[str] = mapped_column(String(30), default="wearable")


class Anthropometrics(Base):
    __tablename__ = "anthropometrics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    height_cm: Mapped[float] = mapped_column(Float, info=HEALTH)
    sitting_height_cm: Mapped[float] = mapped_column(Float, info=HEALTH)
    weight_kg: Mapped[float] = mapped_column(Float, info=HEALTH)


# --------------------------------------------------------------------------- development


class TestResult(Base):
    __tablename__ = "test_results"
    __test__ = False  # not a pytest test class
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    test: Mapped[str] = mapped_column(String(30))  # key in config/norms.yaml
    value: Mapped[float] = mapped_column(Float)


class Drill(Base):
    """Curated library; the Development Coach only picks from here."""

    __tablename__ = "drills"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(120))
    kpi: Mapped[str] = mapped_column(String(30))
    session_type: Mapped[SessionType] = mapped_column(Enum(SessionType))
    description: Mapped[str] = mapped_column(Text)
    typical_rpe: Mapped[float] = mapped_column(Float)
    minutes: Mapped[int] = mapped_column(Integer)
    plyometric: Mapped[bool] = mapped_column(Boolean, default=False)  # restricted in PHV window
    min_age: Mapped[int] = mapped_column(Integer, default=13)


class IDPGoal(Base):
    """Individual development plan goal over a 4-week cycle."""

    __tablename__ = "idp_goals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    kpi: Mapped[str] = mapped_column(String(30))
    baseline_value: Mapped[float] = mapped_column(Float)
    target_value: Mapped[float] = mapped_column(Float)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    sessions_per_week: Mapped[int] = mapped_column(Integer, default=2)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | met | missed | dropped


# --------------------------------------------------------------------------- plans and agents


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    starts_on: Mapped[date] = mapped_column(Date)
    agent_run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | active | superseded
    solver_status: Mapped[str | None] = mapped_column(String(30))  # optimal | relaxed | template
    explanation_player: Mapped[str | None] = mapped_column(Text)  # 3 sentences
    reason_coach: Mapped[str | None] = mapped_column(String(300))  # 1 line
    items: Mapped[list[PlanItem]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class PlanItem(Base):
    __tablename__ = "plan_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("weekly_plans.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    kind: Mapped[SessionType] = mapped_column(Enum(SessionType))
    target_rpe: Mapped[int] = mapped_column(Integer)
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    drill_id: Mapped[str | None] = mapped_column(ForeignKey("drills.id"))
    plan: Mapped[WeeklyPlan] = relationship(back_populates="items")


class AgentRun(Base):
    """Audit trail of one agent invocation: inputs, flags, constraints, solver result."""

    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    agent: Mapped[AgentName] = mapped_column(Enum(AgentName))
    trigger: Mapped[str] = mapped_column(String(50))  # nightly | checkin | flag | test_day | weekly
    player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    constraints: Mapped[dict | None] = mapped_column(JSON)
    output: Mapped[dict | None] = mapped_column(JSON)
    llm_valid_first_try: Mapped[bool | None] = mapped_column(Boolean)
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"))
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # agents.coordinator.ActionKind
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    current_plan_id: Mapped[str | None] = mapped_column(ForeignKey("weekly_plans.id"))
    proposed_plan_id: Mapped[str | None] = mapped_column(ForeignKey("weekly_plans.id"))
    reason: Mapped[str] = mapped_column(String(300))
    data_chips: Mapped[list[str]] = mapped_column(JSON, default=list)  # "Sleep 5.5 h x 3", "Load +60%"
    policy_rule: Mapped[str] = mapped_column(String(200))
    status: Mapped[ProposalStatus] = mapped_column(Enum(ProposalStatus), default=ProposalStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id", ondelete="CASCADE"), unique=True)
    approver_id: Mapped[str] = mapped_column(ForeignKey("staff_members.id"))
    action: Mapped[str] = mapped_column(String(10))  # approve | edit | reject
    note: Mapped[str | None] = mapped_column(String(500))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Escalation(Base):
    """Pain report, red mood or missed check-ins: goes to a named adult, no agent action."""

    __tablename__ = "escalations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # analytics.flags.FlagKind (safety)
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff_members.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # target < 5 min
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    actor_role: Mapped[str] = mapped_column(String(20))  # a Role or an AgentName
    actor_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(30))  # read | create | update | delete | export | approve
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
