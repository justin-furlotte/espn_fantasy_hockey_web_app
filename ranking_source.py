"""ESPN Fantasy Hockey ranking source.

ESPN's public fantasy API is undocumented and can change without notice.
The article rankings are capped at 250; this module pulls the full standard-game
draft ranks that power the actual draft board (practice drafts, live drafts, etc.).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
import json
import requests

# 2026-27 season is labeled 2027 in the Fantasy API
SEASON = 2027
ESPN_BASE = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{SEASON}"
ESPN_LEAGUEDEFAULTS_URL = f"{ESPN_BASE}/segments/0/leaguedefaults/1"
ESPN_ATHLETES_URL = "https://sports.core.api.espn.com/v3/sports/hockey/nhl/athletes"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Fantasy Hockey Draft Board)",
}


def _request_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> Any:
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    response = requests.get(url, params=params, headers=h, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _player_object(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize the two common ESPN response shapes."""
    player = row.get("player")
    return player if isinstance(player, dict) else row


def _standard_rank(player: dict[str, Any]) -> int | None:
    ranks = player.get("draftRanksByRankType") or {}
    standard = ranks.get("STANDARD") if isinstance(ranks, dict) else None
    if isinstance(standard, dict):
        rank = standard.get("rank")
        if rank is not None:
            try:
                rank = int(rank)
                return rank if rank > 0 else None
            except (TypeError, ValueError):
                pass

    # Fallback for older/alternate response shapes
    rankings = player.get("rankings")
    if isinstance(rankings, dict):
        for values in rankings.values():
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, dict) and str(item.get("rankType", "")).upper() == "STANDARD":
                        try:
                            rank = int(item.get("rank"))
                            return rank if rank > 0 else None
                        except (TypeError, ValueError):
                            pass
    return None


def _date_age(dob: str | None, as_of: date | None = None) -> int | None:
    if not dob:
        return None
    try:
        birthday = datetime.fromisoformat(dob.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            birthday = date.fromisoformat(dob[:10])
        except ValueError:
            return None
    today = as_of or date.today()
    return today.year - birthday.year - (
        (today.month, today.day) < (birthday.month, birthday.day)
    )


def fetch_espn_player_pool(limit: int = 500) -> list[dict[str, Any]]:
    """Return ESPN-ranked active players (the ranks used in real/practice drafts).

    Uses the leaguedefaults endpoint + sortDraftRanks filter, which returns the
    same ordering that appears in the ESPN Fantasy draft board.
    """
    fantasy_filter = {
        "players": {
            "limit": limit,
            "sortDraftRanks": {
                "sortPriority": 100,
                "sortAsc": True,
                "value": "STANDARD",
            },
        }
    }

    data = _request_json(
        ESPN_LEAGUEDEFAULTS_URL,
        params={"view": "kona_player_info"},
        headers={"X-Fantasy-Filter": json.dumps(fantasy_filter)},
    )

    rows = data.get("players", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("Unexpected ESPN player response shape")

    output: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        player = _player_object(row)
        rank = _standard_rank(player)
        name = player.get("fullName")
        if not name or rank is None:
            continue

        output.append({
            "Player": str(name),
            "ESPN Ranking": rank,
            "ESPN ID": player.get("id", row.get("id")),
            "Age": player.get("age") or _date_age(player.get("dateOfBirth")),
            "Status": row.get("status") or player.get("status") or player.get("injuryStatus"),
            "Default Position ID": player.get("defaultPositionId"),
        })

    # Deduplicate by name, keeping the best (lowest) rank if any collision occurs
    dedup: dict[str, dict[str, Any]] = {}
    for row in output:
        current = dedup.get(row["Player"])
        if current is None or row["ESPN Ranking"] < current["ESPN Ranking"]:
            dedup[row["Player"]] = row

    return sorted(dedup.values(), key=lambda x: (x["ESPN Ranking"], x["Player"]))


def fetch_espn_ages() -> dict[int, int]:
    """Fetch ESPN's current NHL athlete DOB/age data (all pages).

    Returns a map of ESPN athlete/player ID → age in years.
    """
    ages: dict[int, int] = {}
    page = 1
    page_count = 1  # updated after first response

    while page <= page_count:
        data = _request_json(
            ESPN_ATHLETES_URL,
            params={"limit": 1000, "page": page},
        )
        if not isinstance(data, dict):
            break

        page_count = int(data.get("pageCount") or 1)
        items = data.get("items") or []

        for athlete in items:
            if not isinstance(athlete, dict):
                continue
            try:
                athlete_id = int(athlete["id"])
            except (KeyError, TypeError, ValueError):
                continue

            age = athlete.get("age")
            if age is None:
                age = _date_age(athlete.get("dateOfBirth"))
            if age is None:
                continue
            try:
                ages[athlete_id] = int(age)
            except (TypeError, ValueError):
                pass

        page += 1

    return ages


def get_espn_rankings() -> list[dict[str, Any]]:
    """Fetch the current ESPN ranked player pool with age metadata.

    Output format is identical to the previous implementation:
        [{"Player": str, "ESPN Ranking": int, "ESPN ID": ..., "Age": ...,
          "Status": ..., "Default Position ID": ...}, ...]
    sorted by ESPN Ranking ascending.
    """
    players = fetch_espn_player_pool()
    try:
        ages = fetch_espn_ages()
    except requests.RequestException:
        ages = {}

    for player in players:
        if player["Age"] is None and player.get("ESPN ID") is not None:
            try:
                player["Age"] = ages.get(int(player["ESPN ID"]))
            except (TypeError, ValueError):
                pass
    return players


if __name__ == "__main__":
    rows = get_espn_rankings()
    print(f"Fetched {len(rows):,} ESPN-ranked players")
    for row in rows[:15]:
        print(row)