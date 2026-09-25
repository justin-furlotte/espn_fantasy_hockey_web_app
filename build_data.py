"""Build the static data consumed by the GitHub Pages app.

The site remains static, but ESPN rankings are now fetched from ESPN's
full fantasy player pool rather than manually copied from the 250-player
editorial article.  The browser can also refresh the same source live.
"""

import json
from pathlib import Path

import pandas as pd

from ranking_source import get_espn_rankings

YEARS = list(range(2019, 2027))
ALPHA = 0.75
BASE = Path(__file__).resolve().parent

stats = pd.read_csv(BASE / "data/stats.csv")
stats["Year"] = pd.to_numeric(stats["Year"], errors="coerce").astype("Int64")
stats["PPG"] = pd.to_numeric(stats["PPG"], errors="coerce").fillna(0.0)
stats["GP"] = pd.to_numeric(stats["GP"], errors="coerce").fillna(0.0)

espn_rows = get_espn_rankings()
espn_df = pd.DataFrame(espn_rows)
espn_df = espn_df[["ESPN Ranking", "Player", "Age", "Default Position ID"]].drop_duplicates("Player")
espn_df = espn_df.sort_values(["ESPN Ranking", "Player"]).reset_index(drop=True)
espn_df.to_csv(BASE / "data/espn_rankings.csv", index=False)

# Historical data for the searchable player chart.
players = sorted(set(stats["Player"].dropna()) | set(espn_df["Player"].dropna()))
history = []
for player in players:
    player_stats = stats[stats["Player"].eq(player)].groupby("Year")["PPG"].first()
    player_gp = stats[stats["Player"].eq(player)].groupby("Year")["GP"].first()
    for year in YEARS:
        history.append({
            "player": player,
            "year": int(year),
            "ppg": round(float(player_stats.get(year, 0) or 0), 2),
            "gp": int(round(float(player_gp.get(year, 0) or 0))),
        })

# Attach current PPG and EWMA PPG to every ESPN-ranked player.
ranked = espn_df.copy()
ranked["PPG"] = 0.0
ranked["EWMA PPG"] = 0.0
ranked["Position"] = ""

for idx, player in ranked["Player"].items():
    player_rows = stats[stats["Player"].eq(player)].sort_values("Year")
    ranked.loc[idx, "Position"] = ",".join(
        player_rows["Position"].dropna().astype(str).unique()
    )
    ppg_history = player_rows.set_index("Year")["PPG"].reindex(YEARS, fill_value=0.0)
    ranked.loc[idx, "PPG"] = round(float(ppg_history.iloc[-1]), 2)
    ranked.loc[idx, "EWMA PPG"] = round(
        float(ppg_history.ewm(alpha=ALPHA).mean().iloc[-1]), 2
    )

# The draft board is a skater board, so exclude goalies using the historical
# position labels just as the original app did.
goalie_names = set(stats.loc[stats["Position"].eq("Goalie"), "Player"].dropna())
ranked = ranked[(ranked["Default Position ID"].fillna(0).astype(int) != 5) & ~ranked["Player"].isin(goalie_names)].copy()

ranked = ranked.sort_values(by="PPG", ascending=False, kind="mergesort").reset_index(drop=True)
ranked["PPG Ranking"] = ranked.index + 1
ranked["Steal Value"] = ranked["ESPN Ranking"] - ranked["PPG Ranking"]
ranked = ranked.sort_values(by="Steal Value", ascending=False, kind="mergesort")

ranked_for_json = ranked[
    ["PPG Ranking", "ESPN Ranking", "Player", "Age", "PPG", "EWMA PPG", "Steal Value"]
].copy()

def _json_safe(v):
    """Convert pandas/numpy NaN, NaT, inf to None; leave everything else alone."""
    if v is None:
        return None
    try:
        # catches float nan, numpy nan, pandas NA
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    # reject inf as well
    try:
        if isinstance(v, float) and (v != v or abs(v) == float("inf")):
            return None
    except Exception:
        pass
    return v

# Apply cell-by-cell so no nan can survive
records = []
for row in ranked_for_json.to_dict("records"):
    clean = {k: _json_safe(v) for k, v in row.items()}
    # Age should be int or null
    if clean.get("Age") is not None:
        try:
            clean["Age"] = int(clean["Age"])
        except (TypeError, ValueError):
            clean["Age"] = None
    records.append(clean)

payload = {
    "years": YEARS,
    "history": history,
    "gems": records,
    "updated": pd.Timestamp.today().strftime("%Y-%m-%d"),
    "ewmaAlpha": ALPHA,
    "rankingSource": "ESPN Fantasy API (standard draft rank)",
}

out_path = BASE / "data/app-data.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, separators=(",", ":"), allow_nan=False)

print(f"ESPN rankings: {len(espn_df):,}")
print(f"Gems/skaters: {len(records):,}")
print(f"History rows: {len(history):,}")
print(f"Wrote {out_path}")