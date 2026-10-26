import copy

import pytest

from analytics.load import ewma_acwr_series
from domain.enums import SessionType
from simulator.policies import PlannedSession
from simulator.season import PRESEASON_DAILY_LOAD, SeasonSimulator, load_config


@pytest.fixture(scope="module")
def small_cfg():
    cfg = load_config()
    cfg["n_players"] = 6
    cfg["weeks"] = 12
    return cfg


@pytest.fixture(scope="module")
def season(small_cfg):
    return SeasonSimulator(copy.deepcopy(small_cfg)).run()


def test_same_seed_same_season(small_cfg, season):
    again = SeasonSimulator(copy.deepcopy(small_cfg)).run()
    assert again.daily == season.daily
    assert again.sessions == season.sessions


def test_different_seed_differs(small_cfg, season):
    cfg = copy.deepcopy(small_cfg)
    cfg["seed"] += 1
    assert SeasonSimulator(cfg).run().daily != season.daily


def test_table_sizes(small_cfg, season):
    days = small_cfg["weeks"] * 7
    assert len(season.daily) == small_cfg["n_players"] * days
    assert len(season.checkins) == small_cfg["n_players"] * days
    assert len(season.players) == small_cfg["n_players"]


def test_players_are_13_to_18(season):
    assert all(13 <= p["age_at_start"] < 19 for p in season.players)


def test_matches_fixed_and_one_rest_day(season):
    by_week = {}
    for r in season.daily:
        by_week.setdefault((r["player_id"], r["week"]), []).append(r["load"])
    assert all(loads.count(0.0) >= 1 for loads in by_week.values())
    match_days = {s["date"] for s in season.sessions if s["kind"] == SessionType.MATCH.value}
    assert match_days  # every squad has fixtures


def test_daily_acwr_matches_analytics(season):
    pid = season.players[0]["player_id"]
    rows = [r for r in season.daily if r["player_id"] == pid]
    series = ewma_acwr_series([r["load"] for r in rows], initial=PRESEASON_DAILY_LOAD)
    for row, point in zip(rows, series):
        assert row["acwr"] == pytest.approx(point.ratio, abs=2e-3)


class AllRestPolicy:
    name = "all_rest"

    def plan_week(self, player, ctx, rng):
        return {d: PlannedSession(SessionType.REST, 0, 0) for d in range(7)}


def test_policy_does_not_change_the_world(small_cfg, season):
    """Common random numbers: sleep noise is identical under a different policy,
    except on mornings after evening matches (which both policies share)."""
    other = SeasonSimulator(copy.deepcopy(small_cfg), policy=AllRestPolicy()).run()
    assert [c["sleep_hours"] for c in other.checkins] == [c["sleep_hours"] for c in season.checkins]
    assert [c["completed"] for c in other.checkins] == [c["completed"] for c in season.checkins]
    assert len(other.sessions) < len(season.sessions)


@pytest.mark.parametrize("variant", ["load", "readiness", "random"])
def test_all_injury_variants_run(small_cfg, variant):
    res = SeasonSimulator(copy.deepcopy(small_cfg), injury_variant=variant).run()
    assert res.variant == variant
    assert all(i["out_days"] >= 7 for i in res.injuries)


def test_unknown_variant_rejected(small_cfg):
    with pytest.raises(ValueError):
        SeasonSimulator(copy.deepcopy(small_cfg), injury_variant="magic")


def test_heuristic_coach_follows_the_rules_the_baseline_ignores(small_cfg, season):
    from eval.harness import executed_violations
    from simulator.policies import HeuristicPolicy

    heur = SeasonSimulator(copy.deepcopy(small_cfg), policy=HeuristicPolicy()).run()
    assert sum(executed_violations(season).values()) > 0  # blind template: sessions on exam days, hard MD-1
    assert not executed_violations(heur)
    assert heur.fixtures == season.fixtures  # same world, only the plans differ


def test_seed_summary_is_paired_with_confidence_intervals():
    from eval.seeds import summarise

    rows = [
        {
            "seed": s,
            "variant": v,
            **{
                p: {"acwr_spike_weeks": spikes, "monotony_weeks": 0, "weekly_load_mean": 2000.0, "injuries": inj,
                    "injuries_in_phv": 0, "rule_violations": 0}
                for p, spikes, inj in (("baseline", 50 + s, 40), ("heuristic", 40 + s, 38), ("agents", 20 + s, 37 + s % 2))
            },
        }
        for s in range(4)
        for v in ("load", "readiness", "random")
    ]  # fmt: skip
    s = summarise(rows)["load"]
    assert s["agents"]["acwr_spike_weeks"]["mean"] == 21.5
    red = s["spike_reduction_vs_heuristic_pct"]
    assert red["lo"] < red["mean"] < red["hi"] and 45 < red["mean"] < 50
    inj = s["injury_diff_vs_heuristic"]
    assert inj["lo"] < 0 < inj["hi"] or inj["hi"] < 0  # a CI, not a single number
