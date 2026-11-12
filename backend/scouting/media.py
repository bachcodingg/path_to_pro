"""Real photos for the StatsBomb players and real crests for their clubs, from Wikimedia.

    python -m scouting.media        # about 100 requests to Wikidata and Wikimedia, 5-10 minutes

Writes data/media.json: for each club its English Wikipedia article's crest, and for each
player a photo from Wikimedia Commons with its author and licence. Only links are kept, no
image files: the pages load the images from Wikimedia's servers.

- Players: Wikidata lists every player who was a member of a club (P54). For each club one
  query fetches them all with their names in the main languages and their photo (P18). A
  StatsBomb name ("Lionel Andrés Messi Cuccittini") is matched to one of them when a name of
  his is the same or contained in it ("Lionel Messi"), and he was at the club in the season.
  Two candidates and no way to choose: no photo, rather than the wrong face. Wikidata often
  lacks a recent signing's spell at a club, so a player not found that way is looked up by
  his exact name: a footballer whose clubs include his, or the only footballer of that name.
  Photos on
  Commons are free to reuse with credit (CC BY, CC BY-SA, public domain), and the pages
  show the credit.
- Clubs: the crest from the club's English Wikipedia article. Most are not free licences:
  Wikipedia shows them under fair use, and so does this app, to identify the club. Free
  crests that are kept in the app itself (frontend/src/shared/crests.ts) come first.

The 2024/25 season numbers bring their own photos and crests (API-Football's), so they need
none of this.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

from scouting.competitions import COMPETITIONS

OUT = Path(__file__).parent / "data" / "media.json"
# The crests for the app itself, which draws them by club name (frontend/src/shared/crests.ts)
CRESTS_OUT = Path(__file__).parents[2] / "frontend" / "src" / "shared" / "wikiCrests.json"
CACHE = Path(__file__).parents[2] / ".media-cache"  # the answers, so a second run asks again only for what failed
UA = "PathToPro-media/1.0 (student football analytics project; python urllib)"
PHOTO_PX = 250  # one of Wikimedia's standard thumbnail widths
CREST_PX = 120

# The StatsBomb club names and their English Wikipedia articles
ARTICLES = {
    "AC Ajaccio": "AC Ajaccio", "AC Milan": "AC Milan", "AFC Bournemouth": "AFC Bournemouth",
    "AS Monaco": "AS Monaco FC", "Angers": "Angers SCO", "Arsenal": "Arsenal F.C.",
    "Aston Villa": "Aston Villa F.C.", "Athletic Club": "Athletic Bilbao", "Atlético Madrid": "Atlético Madrid",
    "Augsburg": "FC Augsburg", "Auxerre": "AJ Auxerre", "Barcelona": "FC Barcelona", "Bastia": "SC Bastia",
    "Bayer Leverkusen": "Bayer 04 Leverkusen", "Bayern Munich": "FC Bayern Munich", "Bochum": "VfL Bochum",
    "Bordeaux": "FC Girondins de Bordeaux", "Borussia Dortmund": "Borussia Dortmund",
    "Borussia Mönchengladbach": "Borussia Mönchengladbach", "Celta Vigo": "RC Celta de Vigo",
    "Chelsea": "Chelsea F.C.", "Clermont Foot": "Clermont Foot", "Crystal Palace": "Crystal Palace F.C.",
    "Darmstadt 98": "SV Darmstadt 98", "Eibar": "SD Eibar", "Eintracht Frankfurt": "Eintracht Frankfurt",
    "Espanyol": "RCD Espanyol", "Everton": "Everton F.C.", "FC Heidenheim": "1. FC Heidenheim",
    "FC Köln": "1. FC Köln", "FC Porto": "FC Porto", "FSV Mainz 05": "1. FSV Mainz 05", "Freiburg": "SC Freiburg",
    "Gazélec Ajaccio": "Gazélec Ajaccio", "Getafe": "Getafe CF", "Granada": "Granada CF",
    "Guingamp": "En Avant Guingamp", "Hoffenheim": "TSG Hoffenheim", "Inter Milan": "Inter Milan",
    "Juventus": "Juventus FC", "Las Palmas": "UD Las Palmas", "Leicester City": "Leicester City F.C.",
    "Lens": "RC Lens", "Levante UD": "Levante UD", "Lille": "Lille OSC", "Liverpool": "Liverpool F.C.",
    "Lorient": "FC Lorient", "Lyon": "Olympique Lyonnais", "Manchester City": "Manchester City F.C.",
    "Manchester United": "Manchester United F.C.", "Metz": "FC Metz", "Montpellier": "Montpellier HSC",
    "Málaga": "Málaga CF", "Nantes": "FC Nantes", "Newcastle United": "Newcastle United F.C.",
    "Norwich City": "Norwich City F.C.", "OGC Nice": "OGC Nice", "Olympique de Marseille": "Olympique de Marseille",
    "Paris Saint-Germain": "Paris Saint-Germain FC", "RB Leipzig": "RB Leipzig",
    "RC Deportivo La Coruña": "Deportivo de La Coruña", "Rayo Vallecano": "Rayo Vallecano",
    "Real Betis": "Real Betis", "Real Madrid": "Real Madrid CF", "Real Sociedad": "Real Sociedad",
    "Rennes": "Stade Rennais F.C.", "Saint-Étienne": "AS Saint-Étienne", "Sevilla": "Sevilla FC",
    "Southampton": "Southampton F.C.", "Sporting Gijón": "Sporting de Gijón", "Stade Brestois": "Stade Brestois 29",
    "Stade Malherbe Caen": "Stade Malherbe Caen", "Stade de Reims": "Stade de Reims", "Stoke City": "Stoke City F.C.",
    "Strasbourg": "RC Strasbourg Alsace", "Sunderland": "Sunderland A.F.C.", "Swansea City": "Swansea City A.F.C.",
    "Tottenham Hotspur": "Tottenham Hotspur F.C.", "Toulouse": "Toulouse FC", "Troyes": "ES Troyes AC",
    "Union Berlin": "1. FC Union Berlin", "Valencia": "Valencia CF", "VfB Stuttgart": "VfB Stuttgart",
    "Villarreal": "Villarreal CF", "Watford": "Watford F.C.", "Werder Bremen": "SV Werder Bremen",
    "West Bromwich Albion": "West Bromwich Albion F.C.", "West Ham United": "West Ham United F.C.",
    "Wolfsburg": "VfL Wolfsburg",
}  # fmt: skip
LANGS = ("en", "es", "fr", "de", "it", "pt", "nl")


def _get(url: str, params: dict, tries: int = 8) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    cached = CACHE / f"{hashlib.sha1(full.encode()).hexdigest()}.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    body = urllib.parse.urlencode(params).encode()
    # A long query goes in the body: an address that long is refused (HTTP 431)
    req = (
        urllib.request.Request(url, data=body, headers={"User-Agent": UA})
        if len(full) > 4000
        else urllib.request.Request(full, headers={"User-Agent": UA})
    )
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.load(r)
            CACHE.mkdir(exist_ok=True)
            cached.write_text(json.dumps(d), encoding="utf-8")
            return d
        except (urllib.error.URLError, TimeoutError) as e:
            if i == tries - 1:
                raise
            # Too many requests: wait as long as the server asks, or longer each time
            wait = getattr(e, "headers", None) and e.headers.get("Retry-After")
            time.sleep(int(wait) if wait and str(wait).isdigit() else 15 * (i + 1))
    raise AssertionError


def _norm(name: str) -> str:
    """'Lionel Andrés Messi Cuccittini' -> 'lionel andres messi cuccittini'"""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = s.replace("ø", "o").replace("ß", "ss").replace("ł", "l").replace("đ", "d").replace("ı", "i")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.replace("'", "").replace("’", "")).split())


def _score(statsbomb: str, names: set[str]) -> int:
    """3: the same name; 2: one of his names (2+ words) within the other; 1: a one-word name
    ('Neymar', 'Isco') within it; 0: no match."""
    s = _norm(statsbomb)
    words = s.split()
    best = 0
    for n in map(_norm, names):
        w = n.split()
        if not w:
            continue
        if n == s:
            return 3
        if len(w) >= 2 and len(words) >= 2 and (set(w) <= set(words) or set(words) <= set(w)):
            best = max(best, 2)
        elif len(w) == 1 and w[0] in words and len(w[0]) >= 4:
            best = max(best, 1)
    return best


def _years(season: str) -> tuple[int, int]:
    ys = [int(y) for y in re.findall(r"\d{4}", season)]
    return min(ys), max(ys) + 1


def clubs() -> dict[str, dict]:
    """Each club's Wikidata item and its English Wikipedia crest."""
    out = {}
    names = list(ARTICLES)
    for i in range(0, len(names), 40):
        batch = names[i : i + 40]
        d = _get(
            "https://en.wikipedia.org/w/api.php",
            {
                "action": "query", "format": "json", "redirects": 1, "titles": "|".join(ARTICLES[n] for n in batch),
                "prop": "pageprops|pageimages", "ppprop": "wikibase_item", "piprop": "thumbnail|name",
                "pithumbsize": CREST_PX, "pilicense": "any",
            },
        )  # fmt: skip
        q = d["query"]
        moved = {r["from"]: r["to"] for r in q.get("redirects", [])} | {
            n["from"]: n["to"] for n in q.get("normalized", [])
        }
        pages = {p["title"]: p for p in q["pages"].values()}
        for n in batch:
            t = ARTICLES[n]
            while t in moved:
                t = moved[t]
            p = pages.get(t, {})
            out[n] = {
                "article": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(t.replace(' ', '_'))}",
                "wikidata": p.get("pageprops", {}).get("wikibase_item"),
                "crest": _bare((p.get("thumbnail") or {}).get("source") or "") or None,
                "crest_file": p.get("pageimage"),
            }
    return out


SPARQL = """
SELECT ?p ?img ?start ?end (GROUP_CONCAT(DISTINCT ?n; separator="|") AS ?names) WHERE {
  ?p p:P54 ?st . ?st ps:P54 wd:%s .
  OPTIONAL { ?st pq:P580 ?start } OPTIONAL { ?st pq:P582 ?end }
  OPTIONAL { ?p wdt:P18 ?img }
  { ?p rdfs:label ?n } UNION { ?p skos:altLabel ?n } UNION { ?p wdt:P1477 ?n } UNION { ?p wdt:P1559 ?n }
  FILTER(LANG(?n) IN (%s))
} GROUP BY ?p ?img ?start ?end
"""


def _year(binding: dict, k: str) -> int | None:
    v = binding.get(k, {}).get("value", "")[:4]
    return int(v) if v.isdigit() else None


def squad_history(qid: str) -> dict[str, dict]:
    """Everyone Wikidata has as a member of the club: names, photo file and spells there."""
    langs = ", ".join(f'"{x}"' for x in LANGS)
    d = _get("https://query.wikidata.org/sparql", {"query": SPARQL % (qid, langs), "format": "json"})
    people: dict[str, dict] = {}
    for b in d["results"]["bindings"]:
        pid = b["p"]["value"].rsplit("/", 1)[1]
        e = people.setdefault(pid, {"names": set(), "img": None, "spells": []})
        e["names"] |= set(b["names"]["value"].split("|"))
        if "img" in b:
            e["img"] = urllib.parse.unquote(b["img"]["value"].rsplit("/", 1)[1])
        e["spells"].append((_year(b, "start"), _year(b, "end")))
    return people


def _there(spells: list, years: tuple[int, int]) -> int:
    """2: a dated spell at the club covers the season; 1: only an undated spell could; 0: no.
    A sparse duplicate item (Kylian Mbappé has one, with no dates) loses to the full one."""
    lo, hi = years
    fits = [(s, e) for s, e in spells if (s is None or s <= hi) and (e is None or e >= lo)]
    return 2 if any(s is not None or e is not None for s, e in fits) else int(bool(fits))


def match(name: str, people: dict[str, dict], years: tuple[int, int]) -> str | None:
    """The Wikidata item of the StatsBomb player, or None when no one or more than one fits."""
    scored = [(_score(name, e["names"]), _there(e["spells"], years), pid) for pid, e in people.items()]
    scored = [s for s in scored if s[0] > 0]
    if not scored:
        return None
    top = max(scored)[:2]
    best = [s for s in scored if s[:2] == top]
    if len(best) == 1:
        return best[0][2]
    return None


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
BY_NAME = """
SELECT ?name ?p ?img (GROUP_CONCAT(DISTINCT ?club; separator="|") AS ?clubs) WHERE {
  VALUES ?name { %s }
  ?p rdfs:label|skos:altLabel ?name ; wdt:P106 wd:Q937857 .
  OPTIONAL { ?p wdt:P18 ?img }
  OPTIONAL { ?p wdt:P54 ?club }
} GROUP BY ?name ?p ?img
"""


def _literal(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def search(wanted: dict[tuple[str, str], str | None], batch: int = 40) -> dict[tuple[str, str], tuple[str, str | None]]:
    """By name, for players not found through their clubs. `wanted`: (club, name) -> the club's
    Wikidata item; returns (club, name) -> (Wikidata item, Commons file). A footballer of exactly
    that name (a label or alias in one of LANGS) who played for the club, or else the only
    footballer of that name. One query per `batch` names, not one per player: Wikidata's search
    API soon answers a stream of single requests with HTTP 429."""
    out: dict[tuple[str, str], tuple[str, str | None]] = {}
    names = sorted({name for _, name in wanted})
    for i in range(0, len(names), batch):
        chunk = names[i : i + batch]
        values = " ".join(f"{_literal(n)}@{lang}" for n in chunk for lang in LANGS)
        d = _get("https://query.wikidata.org/sparql", {"query": BY_NAME % values, "format": "json"})
        hits: dict[str, dict[str, tuple[set[str], str | None]]] = {}
        for b in d["results"]["bindings"]:
            pid = b["p"]["value"].rsplit("/", 1)[1]
            img = urllib.parse.unquote(b["img"]["value"].rsplit("/", 1)[1]) if "img" in b else None
            clubs = {c.rsplit("/", 1)[1] for c in b.get("clubs", {}).get("value", "").split("|") if c}
            seen = hits.setdefault(b["name"]["value"], {})
            old = seen.get(pid, (set(), None))
            seen[pid] = (old[0] | clubs, old[1] or img)
        for (team, name), qid in wanted.items():
            if name not in chunk:
                continue
            found = hits.get(name, {})
            at = [pid for pid, (clubs, _) in found.items() if qid in clubs]
            pick = at if at else list(found)
            if len(pick) > 1:  # a sparse duplicate item: keep the one with the fuller club history
                most = max(len(found[x][0]) for x in pick)
                pick = [x for x in pick if len(found[x][0]) == most]
            if len(pick) == 1:
                out[(team, name)] = (pick[0], found[pick[0]][1])
        time.sleep(2)
    return out


def wikipedia_photos(items: list[str]) -> dict[str, str]:
    """Wikidata item -> the free photo in the player's English Wikipedia infobox, for players
    whose Wikidata photo is missing or a wide shot. Freely licensed files only (`pilicense`)."""
    titles: dict[str, str] = {}
    for i in range(0, len(items), 50):
        d = _get(WIKIDATA_API, {"action": "wbgetentities", "format": "json", "ids": "|".join(items[i : i + 50]),
                                "props": "sitelinks", "sitefilter": "enwiki"})  # fmt: skip
        for qid, e in d.get("entities", {}).items():
            if t := e.get("sitelinks", {}).get("enwiki", {}).get("title"):
                titles[t] = qid
        time.sleep(1)
    out: dict[str, str] = {}
    names = sorted(titles)
    for i in range(0, len(names), 50):
        d = _get("https://en.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "redirects": 1, "titles": "|".join(names[i : i + 50]),
            "prop": "pageimages", "piprop": "name", "pilicense": "free",
        })  # fmt: skip
        q = d["query"]
        moved = {r["to"]: r["from"] for r in q.get("redirects", []) + q.get("normalized", [])}
        for page in q.get("pages", {}).values():
            t = page.get("title", "")
            while t not in titles and t in moved:
                t = moved[t]
            if page.get("pageimage") and t in titles:
                out[titles[t]] = page["pageimage"].replace("_", " ")
        time.sleep(1)
    return out


def _group(file: str) -> bool:
    """A file named for several people ("Verratti, Dagba & Paredes") would put the wrong face
    first, unless it has been cropped (to the one player, as "Januzaj and Hazard (cropped)")."""
    return bool(re.search(r" & | and ", file)) and "cropped" not in file.lower()


def _plain(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


WIDEST = 1.2  # width / height: wider than this is a scene, not a portrait


def _bare(url: str) -> str:
    """The image address without the tracking query Wikimedia adds"""
    return url.split("?utm_", 1)[0]


def photo_info(files: list[str]) -> dict[str, dict]:
    """Thumbnail address, author and licence of each Commons file."""
    out = {}
    for i in range(0, len(files), 50):
        batch = files[i : i + 50]
        d = _get(
            "https://commons.wikimedia.org/w/api.php",
            {
                "action": "query", "format": "json", "titles": "|".join(f"File:{f}" for f in batch),
                "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": PHOTO_PX,
                "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl",
            },
        )  # fmt: skip
        q = d["query"]
        back = {n["to"]: n["from"] for n in q.get("normalized", [])}
        for p in q["pages"].values():
            ii = (p.get("imageinfo") or [None])[0]
            if not ii:
                continue
            meta = ii.get("extmetadata", {})
            f = back.get(p["title"], p["title"]).removeprefix("File:")
            if ii.get("width", 0) > WIDEST * ii.get("height", 1):
                continue  # a wide shot: in a small circle, a crowd rather than a face
            out[f] = {
                "url": _bare(ii.get("thumburl") or ii["url"]),
                "page": ii["descriptionurl"],
                "author": _plain(meta.get("Artist", {}).get("value", ""))[:120] or "Unknown author",
                "licence": _plain(meta.get("LicenseShortName", {}).get("value", "")),
                "licence_url": meta.get("LicenseUrl", {}).get("value"),
            }
        time.sleep(2)
    return out


@lru_cache(maxsize=1)
def _photos() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))["players"] if OUT.exists() else {}


def photo(name: str, team: str) -> dict | None:
    """The StatsBomb player's photo: url, Commons page, author and licence; None without one.
    By club and name: two players of one name (Adama Traoré at Aston Villa and at Monaco) are
    two people."""
    p = _photos().get(f"{team}|{name}")
    return {k: p.get(k) for k in ("url", "page", "author", "licence", "licence_url")} if p else None


def build(log=print) -> dict:
    from scouting import style  # here, not at the top: style itself asks this module for photos

    club = clubs()
    log(f"{len(club)} clubs, {sum(bool(c['crest']) for c in club.values())} with a crest")
    # Every player with minutes, by club and name, with the season he was there
    wanted: dict[tuple[str, str], tuple[int, int]] = {}
    for key, c in COMPETITIONS.items():
        for p in style.load(key)["players"]:
            if p["minutes"] > 0:
                wanted.setdefault((p["team"], p["name"]), _years(c.season))
    found: dict[tuple[str, str], str] = {}  # (club, name) -> Commons file
    items: dict[tuple[str, str], str] = {}  # (club, name) -> Wikidata item
    teams = sorted({team for team, _ in wanted})
    for i, team in enumerate(teams, 1):
        qid = (club.get(team) or {}).get("wikidata")
        if not qid:
            log(f"  {team}: no Wikidata item")
            continue
        people = squad_history(qid)
        mine = sorted(name for t, name in wanted if t == team)
        hits = 0
        for name in mine:
            pid = match(name, people, wanted[(team, name)])
            if pid:
                items[(team, name)] = pid
                hits += 1
                if people[pid]["img"]:
                    found[(team, name)] = people[pid]["img"]
        log(f"  {i}/{len(teams)} {team}: {len(people)} in Wikidata, {hits} of {len(mine)} matched")
        time.sleep(1)
    left = {k: (club.get(k[0]) or {}).get("wikidata") for k in sorted(set(wanted) - set(items))}
    log(f"{len(left)} players not found through their clubs: searching by name")
    for k, (pid, img) in search(left).items():
        items[k] = pid
        if img:
            found[k] = img
    found = {k: f for k, f in found.items() if not _group(f)}
    info = photo_info(sorted(set(found.values())))
    # No usable Wikidata photo (none, a group, or a wide shot): the one on his Wikipedia page
    lacking = sorted({items[k] for k in items if found.get(k) not in info})
    log(f"{len(lacking)} without a usable Wikidata photo: trying their English Wikipedia pages")
    extra = wikipedia_photos(lacking)
    for k in items:
        if found.get(k) not in info and items[k] in extra:
            found[k] = extra[items[k]]
    found = {k: f for k, f in found.items() if not _group(f)}
    info |= photo_info(sorted(set(found.values()) - set(info)))
    players = {
        f"{team}|{name}": {"wikidata": items[(team, name)], **info[f]}
        for (team, name), f in sorted(found.items())
        if f in info
    }
    log(f"{len(wanted)} players: {len(items)} found in Wikidata, {len(players)} with a photo")
    return {
        "source": "Wikidata, Wikimedia Commons and English Wikipedia",
        "fetched": time.strftime("%Y-%m-%d"),
        "players_total": len(wanted),  # one per club: a player at two clubs counts twice
        "clubs": club,
        "players": players,
    }


if __name__ == "__main__":
    data = build()
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")  # the same file on Windows as anywhere
    crests = {
        team: {
            "url": c["crest"],
            "file": f"https://en.wikipedia.org/wiki/File:{urllib.parse.quote(c['crest_file'].replace(' ', '_'))}",
        }
        for team, c in sorted(data["clubs"].items())
        if c.get("crest") and c.get("crest_file")
    }
    CRESTS_OUT.write_text(json.dumps(crests, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {OUT} and {CRESTS_OUT}")
