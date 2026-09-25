# ESPN Fantasy Hockey Draft Board

A lightweight, static draft helper designed for GitHub Pages.

## What it does

- **Historical PPG:** searchable player selector, with 2019–2026 ESPN-scoring PPG history. David Pastrnak is selected by default.
- **Gems:** sortable table comparing PPG rank against ESPN rank.
- **Steal Value:** `ESPN Ranking - PPG Ranking`; larger positive values mean ESPN has the player later than the PPG ranking.
- **EWMA PPG:** the same `alpha=0.75` exponentially weighted moving average used by the original analysis.
- **Player Projections:** visual comparison of current PPG and EWMA PPG against ESPN draft rank.

## GitHub Pages

This is a static site. Put the contents of this directory in a GitHub repository and enable GitHub Pages from the repository's main branch.

No server or Python runtime is required for the deployed site.

## Updating the data

The browser uses `data/app-data.json` so the site stays fast.

If you update `data/stats.csv` or the ranking source, run:

```bash
python build_data.py
```

Then commit the regenerated `data/app-data.json`.

The Python build step intentionally contains no ESPN credentials. The historical `stats.csv` is already a cached export from the original project, while `get_espn_rankings()` supplies the current ESPN draft order from the original source code. The GitHub Pages site itself never contacts ESPN.
