"""Ball-skills sessions per position, with the growth-zone, readiness and match-day rules."""

from datetime import date

import pytest

from skills.programme import SkillsContext, build, drills_for, library

DAY = date(2026, 11, 26)


@pytest.mark.parametrize("position", ["goalkeeper", "centre_back", "full_back", "midfielder", "winger", "striker"])
def test_every_position_gets_its_own_drills(position):
    s = build(SkillsContext(position, day=DAY))
    own = [b for b in s.blocks if position in b["positions"]]
    assert s.mode == "full" and len(own) >= 2 and 25 <= s.minutes <= 50
    assert all(b["steps"] and b["cues"] for b in s.blocks)
    assert len(drills_for(position)) >= 9  # own drills + everyone's


def test_library_ids_are_consistent():
    drills, pos, slots = library()
    referenced = {i for p in pos.values() for block in p["blocks"] for i in block} | {p["finish"] for p in pos.values()}
    referenced |= set(slots["warmup"]) | set(slots["shared"])
    assert referenced <= set(drills)
    for d in drills.values():
        assert "jumping" not in d.tags or d.safe_version, d.id  # every jumping drill has a growth-zone version
        assert d.partner in ("none", "optional", "needed")


def test_growth_zone_no_jumps_half_the_kicking():
    normal = {b["id"]: b for b in build(SkillsContext("striker", day=DAY)).blocks}
    growing = build(SkillsContext("striker", in_phv_window=True, day=DAY))
    for b in growing.blocks:
        if "striking" in b["tags"]:
            assert b["reps"] != normal.get(b["id"], b)["reps"] or b["id"] not in normal
        if "jumping" in b["tags"]:
            assert b["variant"]  # done standing, as technique
    assert any("Growth zone" in a for a in growing.adjustments)


def test_red_day_is_technique_only_and_match_day_has_no_session():
    red = build(SkillsContext("winger", band="red", day=DAY))
    assert red.mode == "technique" and red.minutes <= 30
    assert not any({"sprint", "striking", "jumping", "diving"} & set(b["tags"]) for b in red.blocks)
    match_day = build(SkillsContext("winger", days_to_match=0, day=DAY))
    assert match_day.mode == "rest" and len(match_day.blocks) == 1


def test_day_before_a_match_is_short_with_no_sprints():
    s = build(SkillsContext("winger", days_to_match=1, day=DAY))
    assert s.mode == "short" and len(s.blocks) == 3
    assert not any("sprint" in b["tags"] for b in s.blocks)


def test_on_your_own_no_drill_needs_a_partner():
    s = build(SkillsContext("goalkeeper", partner=False, day=DAY))
    assert all(b["partner"] != "needed" for b in s.blocks)
    assert any("No partner" in a for a in s.adjustments)


def test_drills_rotate_week_to_week():
    weeks = {tuple(b["id"] for b in build(SkillsContext("midfielder", day=date(2026, 11, d))).blocks) for d in (2, 9, 16, 23)}
    assert len(weeks) > 1

