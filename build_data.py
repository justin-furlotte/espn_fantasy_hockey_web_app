"""Build the static data consumed by the GitHub Pages app.

Historical stats are loaded from data/stats.csv, exactly as in the original
project after its one-time ESPN API export. ESPN draft rankings are sourced
from get_espn_rankings(), also exactly as in the original project; the raw
list is cached to data/espn_rankings.csv and the transformed web-app payload
is cached to data/app-data.json.
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

# This is the same ranking source used by the original main.py.
espn_names = get_espn_rankings()
espn_df = pd.DataFrame({"ESPN Ranking": range(1, len(espn_names) + 1), "Player": espn_names})
espn_df.to_csv(BASE / "data/espn_rankings.csv", index=False)

# Historical data for the searchable player chart.
players = sorted(set(stats["Player"].dropna()) | set(espn_names))
history = []
for player in players:
    player_stats = stats[stats["Player"].eq(player)].groupby("Year")["PPG"].first()
    player_gp = stats[stats["Player"].eq(player)].groupby("Year")["GP"].first()
    for year in YEARS:
        history.append({
            "player": player,
            "year": year,
            "ppg": round(float(player_stats.get(year, 0) or 0), 2),
            "gp": int(round(float(player_gp.get(year, 0) or 0))),
        })

# Reproduce the original Gems calculation:
# 1) attach current PPG and EWMA PPG to every ESPN-ranked player;
# 2) remove goalies;
# 3) sort by PPG to assign PPG Ranking;
# 4) Steal Value = ESPN Ranking - PPG Ranking.
ranked = espn_df.copy()
ranked["PPG"] = 0.0
ranked["EWMA PPG"] = 0.0
ranked["Position"] = ""

for idx, player in ranked["Player"].items():
    player_rows = stats[stats["Player"].eq(player)].sort_values("Year")
    ranked.loc[idx, "Position"] = ",".join(player_rows["Position"].dropna().astype(str).unique())
    ppg_history = player_rows.set_index("Year")["PPG"].reindex(YEARS, fill_value=0.0)
    ranked.loc[idx, "PPG"] = round(float(ppg_history.iloc[-1]), 2)
    ranked.loc[idx, "EWMA PPG"] = round(float(ppg_history.ewm(alpha=ALPHA).mean().iloc[-1]), 2)

# Original main.py removes goalies based on historical stats.
goalie_names = set(stats.loc[stats["Position"].eq("Goalie"), "Player"].dropna())
ranked = ranked[~ranked["Player"].isin(goalie_names)].copy()

ranked = ranked.sort_values(by="PPG", ascending=False, kind="mergesort").reset_index(drop=True)
ranked["PPG Ranking"] = ranked.index + 1
ranked["Steal Value"] = ranked["ESPN Ranking"] - ranked["PPG Ranking"]
ranked = ranked.sort_values(by="Steal Value", ascending=False, kind="mergesort")

ranked_for_json = ranked[["PPG Ranking", "ESPN Ranking", "Player", "PPG", "EWMA PPG", "Steal Value"]]

payload = {
    "years": YEARS,
    "history": history,
    "gems": ranked_for_json.to_dict("records"),
    "updated": pd.Timestamp.today().strftime("%Y-%m-%d"),
    "ewmaAlpha": ALPHA,
}

with open(BASE / "data/app-data.json", "w") as f:
    json.dump(payload, f, separators=(",", ":"))

print(f"ESPN rankings: {len(espn_names):,}")
print(f"Gems/skaters: {len(ranked):,}")
print(f"History rows: {len(history):,}")
print(f"Top steal: {ranked.iloc[0]['Player']} ({int(ranked.iloc[0]['Steal Value']):+d})")
