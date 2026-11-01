#!/usr/bin/env python3
"""Software Board data builder.

Pulls top-100 rankings from three free, no-key sources and writes JSON for index.html:

  github  -> data/github.json   most stars, repos created in the last 1/2/3/6/12 months
  steam   -> data/steam.json    most played right now, games released in the last 1/2/3/6/12 months
  itunes  -> data/itunes.json   Apple top free chart position, apps released in the last 1/2/3/6/12 months

Usage:  python software.py [all|github|steam|itunes]
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

WINDOWS = [1, 2, 3, 6, 12]          # months; rank key "0" is the All window (any launch date)
TOP_N = 100
DATA_DIR = "data"
STATE_DIR = "state"
UA = {"User-Agent": "software-board/1.0 (+https://github.com)"}

GITHUB_WINDOW_TOP = int(os.environ.get("GITHUB_WINDOW_TOP", "20"))           # repos kept per 1/2/3/6/12 month window (All keeps TOP_N)
STEAM_NEW_CANDIDATES = int(os.environ.get("STEAM_NEW_CANDIDATES", "400"))   # newly released games checked for player counts
STEAM_DETAIL_BUDGET = int(os.environ.get("STEAM_DETAIL_BUDGET", "250"))      # Steam store lookups per run (cached afterwards)
ITUNES_CHART_SIZE = int(os.environ.get("ITUNES_CHART_SIZE", "200"))          # chart positions read from Apple

NOW = datetime.now(timezone.utc)


def cutoff(months):
    return (NOW - timedelta(days=round(months * 30.44))).strftime("%Y-%m-%d")


def get_json(url, params=None, headers=None, retries=3, pause=3):
    h = dict(UA)
    if headers:
        h.update(headers)
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=h, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                time.sleep(pause * (attempt + 1))
                continue
            if r.status_code == 403 and "rate limit" in r.text.lower():
                last = "HTTP 403 rate limit"
                time.sleep(20 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            last = str(e)
            time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def clip(text, n=500):
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:-") + "…"


def save(name, source, metric_label, items):
    os.makedirs(DATA_DIR, exist_ok=True)
    out = {
        "source": source,
        "metric": metric_label,
        "updated": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "items": items,
    }
    with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  wrote data/{name}: {len(items)} items")


# --------------------------------------------------------------------------- GitHub
def fetch_github():
    """One search per window: repos created since the cutoff, sorted by stars, top 100."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")      # optional; the Actions runner supplies one automatically
    if token:
        headers["Authorization"] = f"Bearer {token}"
    items = {}
    for w in [*WINDOWS, 0]:                     # 0 = All: most-starred repos of any age
        data = get_json("https://api.github.com/search/repositories",
                        params={"q": f"created:>={cutoff(w)}" if w else "stars:>20000", "sort": "stars", "order": "desc", "per_page": TOP_N if w == 0 else GITHUB_WINDOW_TOP},
                        headers=headers)
        for i, repo in enumerate((data.get("items") or [])[:TOP_N if w == 0 else GITHUB_WINDOW_TOP], 1):
            key = repo["full_name"]
            it = items.get(key)
            if not it:
                owner = repo.get("owner") or {}
                desc = clip(repo.get("description"))
                if not desc and repo.get("topics"):
                    desc = "Topics: " + ", ".join(repo["topics"][:6])
                it = items[key] = {
                    "id": key,
                    "title": key,
                    "desc": desc or "No description provided.",
                    # org avatar for org-owned repos; owner avatar otherwise; social card if neither exists
                    "image": owner.get("avatar_url") or f"https://opengraph.githubassets.com/1/{key}",
                    "date": (repo.get("created_at") or "")[:10],
                    "url": repo.get("html_url") or f"https://github.com/{key}",
                    "metric": repo.get("stargazers_count", 0),
                    "ranks": {},
                }
            it["metric"] = repo.get("stargazers_count", it["metric"])
            it["ranks"][str(w)] = i
        print(f"  github {w}mo: {len(data.get('items') or [])} repos")
        time.sleep(7 if not token else 2)       # unauthenticated search allows 10 requests a minute
    save("github.json", "github", "stars", list(items.values()))


# --------------------------------------------------------------------------- iTunes
def _itunes_chart():
    """Apple's top free apps chart. Returns [(position, app_id, name, image, date, desc, url)]."""
    rows = []
    try:
        d = get_json(f"https://itunes.apple.com/us/rss/topfreeapplications/limit={ITUNES_CHART_SIZE}/json")
        for pos, e in enumerate((d.get("feed") or {}).get("entry") or [], 1):
            img = (e.get("im:image") or [{}])[-1].get("label", "")
            rows.append((pos, str(e["id"]["attributes"]["im:id"]), e["im:name"]["label"],
                         re.sub(r"/\d+x\d+bb", "/512x512bb", img),
                         ((e.get("im:releaseDate") or {}).get("label") or "")[:10],
                         (e.get("summary") or {}).get("label", ""),
                         (e.get("id") or {}).get("label", "")))
    except Exception as ex:                        # fall back to the newer feed (top 100 only, no descriptions)
        print(f"  legacy feed failed ({ex}); using the 100-app feed")
        d = get_json("https://rss.applemarketingtools.com/api/v2/us/apps/top-free/100/apps.json")
        for pos, e in enumerate((d.get("feed") or {}).get("results") or [], 1):
            rows.append((pos, str(e["id"]), e.get("name", ""), e.get("artworkUrl100", ""),
                         (e.get("releaseDate") or "")[:10], "", e.get("url", "")))
    return rows


def fetch_itunes():
    chart = _itunes_chart()
    info = {}
    ids = [r[1] for r in chart]
    for i in range(0, len(ids), 150):             # lookup gives the original release date and the full description
        try:
            d = get_json("https://itunes.apple.com/lookup", params={"id": ",".join(ids[i:i + 150]), "country": "us"})
            for r in d.get("results", []):
                info[str(r.get("trackId"))] = r
        except Exception as ex:
            print(f"  lookup batch failed: {ex}")
        time.sleep(1)
    apps = []
    for pos, aid, name, img, date, desc, url in chart:
        r = info.get(aid, {})
        apps.append({
            "id": aid,
            "title": r.get("trackName") or name,
            "desc": clip(r.get("description") or desc) or "No description provided.",
            "image": r.get("artworkUrl512") or img,
            "date": (r.get("releaseDate") or date or "")[:10],
            "url": r.get("trackViewUrl") or url,
            "metric": pos,                         # Apple chart position
            "ranks": {},
        })
    for a in apps[:TOP_N]:                        # All: the top 100 chart positions, any release date
        a["ranks"]["0"] = a["metric"]
    for w in WINDOWS:
        c = cutoff(w)
        inwin = [a for a in apps if a["date"] and a["date"] >= c]      # chart order is already best first
        for i, a in enumerate(inwin[:TOP_N], 1):
            a["ranks"][str(w)] = i
        print(f"  itunes {w}mo: {len(inwin)} apps in the top {len(chart)}")
    save("itunes.json", "itunes", "apple ranking", [a for a in apps if a["ranks"]])


# --------------------------------------------------------------------------- Steam
STEAM_DATE_FORMATS = ["%b %d, %Y", "%d %b, %Y", "%B %d, %Y", "%d %B, %Y", "%b %Y", "%B %Y"]


def parse_steam_date(s):
    s = (s or "").strip()
    for f in STEAM_DATE_FORMATS:
        try:
            return datetime.strptime(s, f).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def _walk(obj, key, out):
    """Collect every value stored under `key` anywhere in a JSON structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, (int, str)):
                out.append(int(v))
            else:
                _walk(v, key, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, key, out)


def steam_chart():
    """Most played right now: {appid: players}."""
    for url, field in (("https://api.steampowered.com/ISteamChartsService/GetGamesByConcurrentPlayers/v1/", "concurrent_in_game"),
                       ("https://api.steampowered.com/ISteamChartsService/GetMostPlayedGames/v1/", "peak_in_game")):
        try:
            d = get_json(url)
            ranks = (d.get("response") or {}).get("ranks") or []
            out = {int(r["appid"]): int(r.get(field) or r.get("peak_in_game") or 0) for r in ranks}
            if out:
                return out
        except Exception as ex:
            print(f"  steam chart {url.split('/')[-3]} failed: {ex}")
    return {}


def steam_new_appids():
    """Appids from Steam's Top New Releases pages, newest month first."""
    try:
        d = get_json("https://api.steampowered.com/ISteamChartsService/GetTopReleasesPages/v1/")
    except Exception as ex:
        print(f"  top releases failed: {ex}")
        return []
    pages = (d.get("response") or {}).get("pages") or []
    pages = sorted(pages, key=lambda p: p.get("start_of_month", 0), reverse=True)[:WINDOWS[-1] + 1]
    ids = []
    for p in pages:
        found = []
        _walk(p.get("item_ids", p), "appid", found)
        ids += found
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def steam_players(appid):
    try:
        d = get_json("https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
                     params={"appid": appid}, retries=2, pause=2)
        return int((d.get("response") or {}).get("player_count") or 0)
    except Exception:
        return None


def steam_details(appid):
    try:
        d = get_json("https://store.steampowered.com/api/appdetails",
                     params={"appids": appid, "cc": "us", "l": "english"}, retries=2, pause=5)
        e = (d.get(str(appid)) or {})
        if not e.get("success"):
            return {"skip": True}
        g = e["data"]
        rd = g.get("release_date") or {}
        return {
            "name": g.get("name", ""),
            "type": g.get("type", ""),
            "desc": clip(g.get("short_description") or g.get("about_the_game")),
            "image": g.get("header_image", ""),
            "date": "" if rd.get("coming_soon") else parse_steam_date(rd.get("date")),
        }
    except Exception:
        return None


def fetch_steam():
    os.makedirs(STATE_DIR, exist_ok=True)
    cache_path = os.path.join(STATE_DIR, "steam_cache.json")
    try:
        cache = json.load(open(cache_path, encoding="utf-8"))
    except Exception:
        cache = {}

    players = steam_chart()
    print(f"  steam chart: {len(players)} games")
    oldest = cutoff(WINDOWS[-1])
    today = NOW.strftime("%Y-%m-%d")

    # newly released games that are not on the chart still need a player count
    extra = [a for a in steam_new_appids() if a not in players]
    extra = [a for a in extra if not (cache.get(str(a), {}).get("date") and cache[str(a)]["date"] < oldest)]
    extra = extra[:STEAM_NEW_CANDIDATES]
    print(f"  steam new releases to count: {len(extra)}")
    for a in extra:
        n = steam_players(a)
        if n is not None:
            players[a] = n
        time.sleep(0.25)

    # release date, description and header image come from the store (cached forever once found)
    budget = STEAM_DETAIL_BUDGET
    for a in sorted(players, key=lambda x: -players[x]):
        k = str(a)
        if k in cache or budget <= 0:
            continue
        det = steam_details(a)
        budget -= 1
        if det is not None:
            cache[k] = det
        time.sleep(1.6)                           # the store API allows roughly 200 requests per 5 minutes
    json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    skip_types = {"dlc", "demo", "mod", "music", "video", "episode", "series", "advertising"}
    games = []
    for a, n in players.items():
        c = cache.get(str(a))
        if not c or c.get("skip") or not c.get("name") or c.get("type") in skip_types:
            continue
        games.append({
            "id": str(a),
            "title": c["name"],
            "desc": c.get("desc") or "No description provided.",
            "image": c.get("image") or f"https://cdn.cloudflare.steamstatic.com/steam/apps/{a}/header.jpg",
            "date": c.get("date", ""),
            "url": f"https://store.steampowered.com/app/{a}/",
            "metric": n,
            "ranks": {},
        })
    games.sort(key=lambda g: -g["metric"])
    for i, g in enumerate(games[:TOP_N], 1):      # All: most played right now, any release date
        g["ranks"]["0"] = i
    print(f"  steam all: {len(games)} games")
    for w in WINDOWS:
        c = cutoff(w)
        inwin = [g for g in games if g["date"] and c <= g["date"] <= today]
        for i, g in enumerate(inwin[:TOP_N], 1):
            g["ranks"][str(w)] = i
        print(f"  steam {w}mo: {len(inwin)} games")
    save("steam.json", "steam", "most played", [g for g in games if g["ranks"]])


# --------------------------------------------------------------------------- main
JOBS = {"github": fetch_github, "steam": fetch_steam, "itunes": fetch_itunes}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    names = list(JOBS) if which == "all" else [which]
    failed = []
    for n in names:
        if n not in JOBS:
            sys.exit(f"unknown source {n!r}; use all, github, steam or itunes")
        print(f"[{n}]")
        try:
            JOBS[n]()
        except Exception as ex:                   # a failed source keeps its previous JSON file
            print(f"  {n} FAILED: {ex}")
            failed.append(n)
    if failed and len(failed) == len(names):
        sys.exit(1)


if __name__ == "__main__":
    main()
