from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DbSession

from domain.enums import Role, SessionType
from domain.models import Base, Guardian, PlanItem, Player, Squad, StaffMember, WeeklyPlan, health_columns

PLAN_ENTITIES = {
    "players", "guardians", "squads", "staff_members", "sessions", "matches", "session_loads",
    "wellness_checkins", "sleep_records", "hrv_records", "anthropometrics", "test_results", "idp_goals",
    "drills", "weekly_plans", "plan_items", "agent_runs", "proposals", "approvals", "escalations",
    "consent_records", "audit_log",
}  # fmt: skip


EXTRA = {"player_guardians", "user_accounts", "player_notes", "task_completions", "daily_status", "app_settings", "staff_ratings", "amateur_profiles", "registrations", "appearances", "career_seasons", "device_tokens", "contracts", "recurring_items", "ledger_entries"}


def test_all_22_plan_entities_exist():
    tables = set(Base.metadata.tables) - EXTRA
    assert tables == PLAN_ENTITIES


def test_health_fields_are_encrypted_at_rest():
    from sqlalchemy import text

    from domain.models import HRVRecord

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with DbSession(engine) as db:
        squad = Squad(name="U15", age_group="U15")
        player = Player(squad=squad, display_name="P", birth_date=date(2011, 1, 1), sex="male")
        db.add_all([squad, player])
        db.flush()
        db.add(HRVRecord(player_id=player.id, day=date(2026, 10, 1), ln_rmssd=4.21))
        db.commit()
        raw = db.execute(text("select ln_rmssd from hrv_records")).scalar_one()
        assert "4.21" not in raw and raw.startswith("gAAAA")  # Fernet token
        assert db.scalars(select(HRVRecord)).one().ln_rmssd == 4.21


def test_health_fields_are_tagged():
    tagged = health_columns()
    assert {"sleep_quality", "fatigue", "stress", "soreness", "mood_red", "pain_reported"} <= set(
        tagged["wellness_checkins"]
    )
    assert tagged["hrv_records"] == ["ln_rmssd"]
    assert "players" not in tagged


def test_create_schema_and_round_trip():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with DbSession(engine) as db:
        squad = Squad(name="U15 Academy", age_group="U15")
        coach = StaffMember(name="Coach A", email="coach@example.org", role=Role.COACH)
        player = Player(squad=squad, display_name="Player 01", birth_date=date(2011, 5, 1), sex="male")
        player.guardians.append(Guardian(name="Guardian 01", email="g1@example.org"))
        db.add_all([squad, coach, player])
        db.flush()
        plan = WeeklyPlan(player_id=player.id, starts_on=date(2026, 10, 19))
        plan.items.append(PlanItem(day=date(2026, 10, 19), kind=SessionType.RECOVERY, target_rpe=3, minutes=45))
        db.add(plan)
        db.commit()

        got = db.scalars(select(WeeklyPlan)).one()
        assert got.items[0].kind == SessionType.RECOVERY
        assert db.scalars(select(Player)).one().guardians[0].name == "Guardian 01"


def test_old_database_gets_new_columns():
    """A database created before positions/pathways existed is upgraded in place."""
    from sqlalchemy import inspect, text

    from api.db import add_missing_columns

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("create table players (id varchar(36) primary key, display_name varchar(100))"))
        conn.execute(text("insert into players values ('a', 'Old Player')"))
        conn.execute(text("create table guardians (id varchar(36) primary key, name varchar(100), email varchar(200))"))
    added = add_missing_columns(engine)
    assert {"players.position", "players.pathway", "guardians.invite_code"} <= set(added)
    with engine.connect() as conn:
        assert conn.execute(text("select position, pathway from players")).one() == ("midfielder", "academy")
    assert any(i["name"] == "ix_guardians_invite_code" for i in inspect(engine).get_indexes("guardians"))
