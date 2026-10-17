"""Gym programmes: shared block for everyone, position block, and the safety adjustments."""

from datetime import date

import pytest

from gym.programme import GymContext, build, library, positions, stage_for

DAY = date(2026, 10, 20)


def _items(p):
    return [it for b in p.blocks for it in b["items"]]


def test_library_is_consistent():
    ex, shared, pos = library()
    assert set(pos) == {"goalkeeper", "centre_back", "full_back", "midfielder", "winger", "striker"}
    for e in ex.values():
        assert e.kind in {"prep", "power", "strength", "prevention", "core", "mobility"}
        if e.alternative:
            assert e.alternative in ex


@pytest.mark.parametrize("position", sorted(positions()))
def test_every_position_gets_shared_and_position_work(position):
    p = build(GymContext(position=position, age=17, maturity="post_phv", day=DAY))
    tags = {b["tag"] for b in p.blocks}
    assert tags == {"everyone", "position"}
    names = {it["id"] for it in _items(p)}
    assert {"nordic", "copenhagen"} <= names  # injury prevention for every footballer
    assert p.position == position and p.focus
    assert len(names) == len(_items(p))  # no exercise twice


def test_positions_differ():
    a = build(GymContext(position="goalkeeper", age=17, maturity="post_phv", day=DAY))
    b = build(GymContext(position="striker", age=17, maturity="post_phv", day=DAY))
    pos_a = {it["id"] for it in _items(a) if it["tag"] == "position"}
    pos_b = {it["id"] for it in _items(b) if it["tag"] == "position"}
    assert pos_a and pos_b and pos_a.isdisjoint(pos_b)


def test_growth_zone_has_no_jumps_or_heavy_loads():
    for position in positions():
        p = build(GymContext(position=position, age=14, maturity="circa_phv", in_phv_window=True, day=DAY))
        assert p.stage == "foundation"
        assert not any(it["plyometric"] or it["heavy"] for it in _items(p))
        assert any("Growth zone" in n for n in p.adjustments)


def test_heavy_lifts_only_post_phv_16_plus():
    assert stage_for(GymContext(age=17, maturity="post_phv")) == "performance"
    assert stage_for(GymContext(age=15, maturity="post_phv")) == "development"
    assert stage_for(GymContext(age=13, maturity="pre_phv")) == "foundation"
    young = build(GymContext(position="centre_back", age=15, maturity="post_phv", day=DAY))
    assert not any(it["heavy"] for it in _items(young))


def test_red_day_is_recovery_only():
    p = build(GymContext(position="winger", age=17, maturity="post_phv", band="red", day=DAY))
    assert p.title == "Recovery gym"
    kinds = {b["kind"] for b in p.blocks}
    assert kinds <= {"prep", "prevention", "core", "mobility"}
    assert "nordic" not in {it["id"] for it in _items(p)}


def test_amber_day_one_set_less_and_no_jumps():
    green = build(GymContext(position="striker", age=17, maturity="post_phv", day=DAY))
    amber = build(GymContext(position="striker", age=17, maturity="post_phv", band="amber", day=DAY))
    assert not any(it["plyometric"] for it in _items(amber))
    g = {it["id"]: it["sets"] for it in _items(green)}
    a = {it["id"]: it["sets"] for it in _items(amber)}
    common = [k for k in g if k in a and k.startswith(("rdl", "pull-up"))]
    assert common and all(a[k] <= g[k] for k in common)


def test_match_proximity():
    md1 = build(GymContext(position="striker", age=17, maturity="post_phv", days_to_match=1, day=DAY))
    assert md1.title == "Pre-match activation"
    assert not any(it["plyometric"] or it["kind"] == "strength" if "kind" in it else it["plyometric"] for it in _items(md1))
    assert "Strength" not in {b["title"] for b in md1.blocks}
    md2 = build(GymContext(position="striker", age=17, maturity="post_phv", days_to_match=2, day=DAY))
    assert "nordic" not in {it["id"] for it in _items(md2)}


@pytest.mark.parametrize("equipment", ["none", "home"])
def test_no_gym_needed(equipment):
    from gym.programme import EQUIPMENT

    for position in positions():
        p = build(GymContext(position=position, age=17, maturity="post_phv", equipment=equipment, day=DAY))
        assert all(it["equipment"] in EQUIPMENT[equipment] for it in _items(p))
        assert len(_items(p)) >= 8


def test_deterministic_and_rotates_weekly():
    ctx = GymContext(position="midfielder", age=17, maturity="post_phv", day=DAY)
    assert build(ctx).to_json() == build(ctx).to_json()
    weeks = {tuple(it["id"] for it in _items(build(GymContext(position="midfielder", age=17, maturity="post_phv", day=date(2026, 9, 7 + 7 * k))))) for k in range(4)}
    assert len(weeks) > 1
