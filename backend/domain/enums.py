"""Enums shared by the domain model, simulator, planner and agents."""

from enum import Enum


class SessionType(str, Enum):
    REST = "rest"
    RECOVERY = "recovery"
    TECHNICAL = "technical"
    TACTICAL = "tactical"
    STRENGTH = "strength"
    SPEED = "speed"
    MATCH = "match"


class Role(str, Enum):
    PLAYER = "player"
    GUARDIAN = "guardian"
    COACH = "coach"
    PHYSIO = "physio"
    ADMIN = "admin"


class ConsentDataType(str, Enum):
    WELLNESS = "wellness"
    SLEEP = "sleep"
    HRV = "hrv"
    ANTHROPOMETRICS = "anthropometrics"
    TEST_RESULTS = "test_results"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    AUTO_APPLIED = "auto_applied"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    SUPERSEDED = "superseded"  # a newer proposal for the same player replaced it


class AgentName(str, Enum):
    MONITOR = "monitor"
    PLANNER = "planner"
    DEVELOPMENT_COACH = "development_coach"
    COORDINATOR = "coordinator"


class Position(str, Enum):
    """Playing position; the gym programme adds a position block on top of the shared one."""

    GOALKEEPER = "goalkeeper"
    CENTRE_BACK = "centre_back"
    FULL_BACK = "full_back"
    MIDFIELDER = "midfielder"
    WINGER = "winger"
    STRIKER = "striker"


class Pathway(str, Enum):
    ACADEMY = "academy"  # club staff plan and approve
    AMATEUR = "amateur"  # self-guided: levels, benchmarks, own club schedule
