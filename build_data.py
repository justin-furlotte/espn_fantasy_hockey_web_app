"""Build the static data consumed by the GitHub Pages app.

The site remains static, but ESPN rankings are now fetched from ESPN's
full fantasy player pool rather than manually copied from the 250-player
editorial article.  The browser can also refresh the same source live.
"""

import json
from pathlib import Path
from espn_api.hockey import League
import pandas as pd
import os
from dotenv import load_dotenv
from ranking_source import get_espn_rankings

# Load environment variables
load_dotenv()
LEAGUE_ID = int(os.getenv("LEAGUE_ID"))
ESPN_S2 = os.getenv("ESPN_S2")
SWID = os.getenv("SWID")
MIN_YEAR = int(os.getenv("MIN_YEAR"))
MAX_YEAR = int(os.getenv("MAX_YEAR"))

YEARS = list(range(MIN_YEAR, MAX_YEAR))
ALPHA = 0.75
BASE = Path(__file__).resolve().parent


def calculate_points(player, year: int) -> dict:
    player_stats = player.stats
    if f"Total {year}" not in player_stats:
        return {"Total Points": 0, "PPG": 0, "GP": 0}
    else:
        x = player_stats[f"Total {year}"]["total"]

        # League scoring formula
        if "G" in x:  # Skaters
            games_played = x["GP"]
            if games_played == 0:
                score = 0
            else:
                score = 3 * x["G"] + 2 * x["A"] + x["G"] + x["A"] + x["+/-"] + 0.3 * x["PIM"] + x["PPG"] + 0.5 * x["PPA"] + x[
                    "PPG"] + x["PPA"] + 2 * x["SHG"] + x["SHA"] + x["SHP"] + x["GWG"] + 0.2 * x["SOG"] + 0.3 * x["HIT"] + 0.5 * \
                        x["BLK"]
                if "DEF" in x:
                    score += x["DEF"]
                if "HAT" in x:
                    score += 10 * x["HAT"]
        elif "GS" in x:  # Goalies
            games_played = x["GS"]
            if games_played == 0:
                score = 0
            else:
                score = x["GS"] + 5 * x["W"] - 2 * x["L"] - x["GA"] + 0.22 * x["SV"] + 3 * x["SO"] + 2 * x["OTL"]
        else:
            raise ValueError(f"Unrecognized player: {player}")
        if games_played == 0:
            ppg = 0
        else:
            ppg = score / games_played
        return {"Total Points": score, "PPG": ppg, "GP": games_played}


def get_player_stats_single_league(league) -> pd.DataFrame:
    # Get free agents
    free_agents = league.free_agents(size=-1)

    # Get rostered players
    teams = league.teams
    still_rostered = []
    for i in range(len(teams)):
        still_rostered += league.teams[i].roster

    players = free_agents + still_rostered
    stats = pd.DataFrame(columns=["PPG", "Total Points", "GP", "Position", "Year"])
    stats.index.name = "Player"
    year = league.year
    for player in players:
        points = calculate_points(player=player, year=year)
        stats.loc[player.name, "PPG"] = round(points["PPG"], 2)
        stats.loc[player.name, "Total Points"] = points["Total Points"]
        stats.loc[player.name, "GP"] = round(points["GP"])
        stats.loc[player.name, "Year"] = year
        stats.loc[player.name, "Position"] = player.position

    return stats


def get_player_stats(
        years: list[int],
        league_id: int = LEAGUE_ID,
        espn_s2: str = ESPN_S2,
        swid: str = SWID
) -> pd.DataFrame:
    stats = []
    for year in years:
        league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)
        stats_year = get_player_stats_single_league(league=league)
        stats.append(stats_year.reset_index())
    stats = pd.concat(stats)
    return stats


# Build player stats df
# Takes about 10 seconds using API. For speed, comment this out and just load it as a csv once you've run it once
stats = get_player_stats(years=YEARS)
stats.to_csv(BASE / "data/stats.csv", index=False)
stats = pd.read_csv(BASE / "data/stats.csv")

# Build ESPN ranking data
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

def position_label(default_position_id, historical_positions: str = "") -> str:
    """Map ESPN slot / historical labels to F or D only."""
    try:
        pid = int(default_position_id)
    except (TypeError, ValueError):
        pid = 0
    # ESPN hockey: 1=C, 2=LW, 3=RW, 4=D, 5=G
    if pid == 4:
        return "D"
    if pid in (1, 2, 3):
        return "F"
    hist = (historical_positions or "").lower()
    if "defen" in hist or hist.strip() in {"d", "ld", "rd"}:
        return "D"
    if any(tok in hist for tok in ("center", "wing", "forward", "c", "lw", "rw", "f")):
        return "F"
    return "F"


# Attach current PPG and EWMA PPG to every ESPN-ranked player.
ranked = espn_df.copy()
ranked["PPG"] = 0.0
ranked["EWMA PPG"] = 0.0
ranked["Position"] = ""

for idx, player in ranked["Player"].items():
    player_rows = stats[stats["Player"].eq(player)].sort_values("Year")
    historical = ",".join(
        player_rows["Position"].dropna().astype(str).unique()
    )
    ranked.loc[idx, "Position"] = position_label(
        ranked.loc[idx, "Default Position ID"], historical
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
    ["PPG Ranking", "ESPN Ranking", "Player", "Position", "Age", "PPG", "EWMA PPG", "Steal Value"]
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