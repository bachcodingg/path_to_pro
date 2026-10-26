"""The competitions in the pro-league analysis, and how much of each the open data covers.

StatsBomb's open data has full seasons for some leagues, one club's season for others,
and only the final for the Champions League. The coverage decides what can be said:

  league  every match of the season: teams are ranked and compared with the rest of the league
  club    every match of one club: that club against its opponents in those matches, no ranks
  finals  one match a season: a match centre per final, no team comparison
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class Competition:
    key: str  # in URLs
    name: str
    season: str
    file: str  # data/<file>.json (set pieces) and data/<file>_play.json
    statsbomb_id: int
    statsbomb_seasons: tuple[int, ...]
    coverage: str  # league | club | finals
    note: str
    featured: str | None = None  # club coverage: the club whose season it is

    @property
    def set_piece_path(self) -> Path:
        return DATA_DIR / f"{self.file}.json"

    @property
    def play_path(self) -> Path:
        return DATA_DIR / f"{self.file}_play.json"

    @property
    def compare_label(self) -> str:
        """What a team's numbers are compared with."""
        return {"league": "league", "club": "opponents", "finals": "other finalist"}[self.coverage]

    def to_json(self) -> dict:
        return {
            "id": self.key,
            "name": self.name,
            "season": self.season,
            "coverage": self.coverage,
            "note": self.note,
            "featured": self.featured,
            "compare_label": self.compare_label,
        }


COMPETITIONS: dict[str, Competition] = {
    c.key: c
    for c in (
        Competition("la-liga", "La Liga", "2015/16", "laliga_2015_16", 11, (27,), "league", "All 380 matches."),
        Competition(
            "premier-league", "Premier League", "2015/16", "premier_league_2015_16", 2, (27,), "league",
            "All 380 matches: Leicester City's title season.",
        ),
        Competition(
            "ligue-1", "Ligue 1", "2015/16", "ligue1_2015_16", 7, (27,), "league",
            "377 of the 380 matches; the open data leaves three out, so a few teams have 37.",
        ),
        Competition(
            "bundesliga", "Bundesliga", "2023/24", "bundesliga_2023_24", 9, (281,), "club",
            "Bayer Leverkusen's 34 matches, the season they won the league unbeaten. Only their matches are in "
            "the open data, so Leverkusen are compared with their opponents, not ranked.",
            featured="Bayer Leverkusen",
        ),
        Competition(
            "champions-league", "Champions League", "Finals 2004-2019", "champions_league_finals", 16,
            (44, 37, 39, 41, 21, 22, 23, 24, 25, 26, 27, 2, 1, 4), "finals",
            "The open data has the final of each season (14 finals from 2004 to 2019), not the earlier rounds.",
        ),
    )
}  # fmt: skip
DEFAULT = "la-liga"


def get(key: str) -> Competition | None:
    return COMPETITIONS.get(key)
