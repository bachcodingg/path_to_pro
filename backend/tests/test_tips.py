"""Match tips: mindset and every position, and the tip picked for today."""

from datetime import date

from skills.programme import library, positions
from tips.library import library as tips_library
from tips.library import tip_for_day

DAY = date(2026, 11, 26)


def test_tips_cover_mindset_and_every_position():
    lib = tips_library()
    assert {t["id"] for t in lib["mindset"]} >= {"mistake-reset", "confidence", "pre-match-nerves", "after-bad-game"}
    assert set(lib["positions"]) == set(positions())
    titles = {t["title"] for ts in lib["positions"].values() for t in ts}
    assert "Positioning as a striker" in titles and "Defending as a left back" in titles
    drill_ids = set(library()[0])
    for ts in lib["positions"].values():
        for t in ts:
            assert t["steps"] and t.get("drill", next(iter(drill_ids))) in drill_ids


def test_tip_for_today_follows_the_match_calendar():
    assert tip_for_day("striker", DAY, days_to_match=0, match_yesterday=False)["reason"] == "Match day"
    assert tip_for_day("striker", DAY, days_to_match=5, match_yesterday=True)["id"] == "after-bad-game"
    week = [tip_for_day("full_back", date(2026, 11, d), 5, False) for d in range(2, 9)]
    assert {t["reason"] for t in week} == {"For your position", "Mindset"} and len({t["id"] for t in week}) >= 4

