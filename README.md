# ESPN Fantasy Hockey Draft Board

A lightweight static draft helper designed for GitHub Pages.

## What it does

- **Historical PPG:** searchable player selector, with 2019–2026 ESPN-scoring PPG history.
- **Gems:** sortable table comparing historical PPG rank against ESPN's current standard-game draft rank.
- **Player age:** pulled from ESPN athlete metadata when available.
- **Steal Value:** `ESPN Ranking - PPG Ranking`; larger positive values mean ESPN has the player later than the PPG ranking.
- **EWMA PPG:** the same `alpha=0.75` exponentially weighted moving average used by the original analysis.
- **Draft tracker:** search for a player and remove them from the board as they are drafted. Exclusions persist in the browser and can be restored individually or reset.
- **Live ESPN refresh:** the **Refresh ESPN Data** button pulls ESPN's full ranked fantasy player pool instead of relying on the ESPN article's top-250 list.
- **Cached fallback:** the site still loads from `data/app-data.json`, so it remains fast and usable if ESPN is temporarily unavailable.

## ESPN ranking source

The old version manually embedded the first 250 names from ESPN's editorial ranking article. ESPN's Fantasy API contains a much larger player pool and stores the standard-game draft rank on each player. The app uses that source.

The live browser refresh uses:

```text
https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2026/players
```

with ESPN's `players_wl` view and the `X-Fantasy-Filter` header to request the full active player pool.

ESPN's Fantasy API is an undocumented internal API and can change without notice. The app therefore keeps the cached JSON fallback and the repository updater described below.

## Updating the cached data

The Python build step now fetches ESPN rankings and ages automatically:

```bash
python -m pip install pandas requests
python build_data.py
```

It regenerates:

- `data/espn_rankings.csv`
- `data/app-data.json`

The repository also includes a GitHub Actions workflow at `.github/workflows/update-data.yml`. It can be run manually from **Actions → Refresh ESPN fantasy data → Run workflow**, and it also runs daily.

## GitHub Pages

Put the repository on GitHub and enable GitHub Pages from the repository's main branch. No server or database is required for the deployed app.

## Important limitation

The live **Refresh ESPN Data** button updates the current browser session. It does not write to GitHub (a static GitHub Pages site cannot safely contain a GitHub write token). The scheduled/manual GitHub Action is what updates the cached data for everyone.
