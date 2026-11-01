# Software Board

A static board of new software, ranked three ways, in the same style as the Movie Board. Everything uses **free APIs that need no key**. GitHub Actions fetch the data daily and commit it as JSON, and `index.html` (GitHub Pages) reads those files.

| Source | Ranked by | Date shown | API |
|---|---|---|---|
| GitHub | Most stars | Repo created | `api.github.com/search/repositories` (`created:>=`, `sort=stars`) |
| Steam | Most played (players in game now) | Game release date | `ISteamChartsService`, `ISteamUserStats/GetNumberOfCurrentPlayers`, store `appdetails` |
| iTunes | Apple ranking (Top Free Apps chart position) | App release date | `itunes.apple.com/.../topfreeapplications` feed and `itunes.apple.com/lookup` |

## Files

| File | What it is |
|---|---|
| `index.html` | The page |
| `software.py` | Does all the work: `python software.py all` (or `github`, `steam`, `itunes`) |
| `.github/workflows/software-daily.yml` | Daily at 06:17 UTC; also runnable from the Actions tab |
| `data/github.json`, `steam.json`, `itunes.json` | One file per source |
| `state/steam_cache.json` | Steam release date, description and header image per game, so each is looked up once |
| `requirements.txt` | `requests` |

## The page

* **Source:** GitHub, Steam, iTunes.
* **Time frame:** 1, 2, 3, 6, 12 months by launch date, or **All** (the all-time top 100 for that source: most-starred repos, most-played Steam games right now, Apple chart top 100). The rank on each tile is the rank *within that window*.
* **Links:** every item links to its own page (GitHub repo, Steam store page, App Store page) from the title, the image, and an Open button (tiles) or Link column (rows).
* **Layout:** Tiles or Rows. **Sort:** Ranking or Newest. **★ Favorites** is kept in your browser.
* **Bottom of each tile (next to the date):** stars, players now, or Apple chart position.
* **Images:** GitHub owner avatar (org avatar for org repos; GitHub's social card if there is no avatar), Steam header image, iTunes app icon.
* **Descriptions:** GitHub repo description (falls back to its topics, then "No description provided."), Steam short description, App Store description.

## JSON format

`data/<source>.json`: `{"source", "metric", "updated", "items": [...]}`. Each item:

| Field | Meaning |
|---|---|
| `id`, `title`, `desc`, `image`, `url`, `date` | Identity, summary, image, link and launch date (`YYYY-MM-DD`) |
| `metric` | Stars, players in game, or Apple chart position |
| `ranks` | `{"1": 4, "3": 9, "0": 2, ...}` (`0` = All) rank inside each window the item belongs to (a missing window means it is not in that window's top 100) |

## Setup

1. Put these files in a new GitHub repo named `software`.
2. **Settings > Actions > General > Workflow permissions:** Read and write.
3. **Settings > Pages:** deploy from the main branch, root folder.
4. **Actions** tab: run *Update software rankings*.

No secrets are needed. The workflow passes the built-in `GITHUB_TOKEN` only to raise GitHub's search limit; the script works without it.

Run locally: `pip install -r requirements.txt`, `python software.py all`, then `python -m http.server` and open `http://localhost:8000`.

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `STEAM_NEW_CANDIDATES` | 400 | Newly released Steam games whose player counts are checked each run |
| `STEAM_DETAIL_BUDGET` | 250 | Steam store lookups per run (results are cached, so the first runs fill in gradually) |
| `ITUNES_CHART_SIZE` | 200 | Chart positions read from Apple |

## Limits and notes

* **A source that fails keeps its previous JSON file**, and the other sources still update.
* **Apple:** only apps inside the chart can appear, so short windows can have few apps. The ranking shown is the real chart position, which can be above 100 because 200 positions are read.
* **Steam:** games not on the Most Played chart are found through Steam's Top New Releases list and their player counts are fetched one by one. The first run or two fill the cache; later runs are quick.
* **GitHub:** `created_at` is the repo creation date, not necessarily when the software launched.
* The Steam and Apple endpoints are not formally documented. The script was tested against mock responses only, so check the first workflow run's log.
