"""ESPN Fantasy Hockey ranking source.

ESPN's public fantasy API is undocumented and can change without notice.  The
article rankings are capped at 250, so this module uses ESPN's player pool,
where ESPN stores the actual standard-game draft rank for the full ranked pool.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
import requests

ESPN_BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/2026"
ESPN_PLAYERS_URL = f"{ESPN_BASE}/players"
ESPN_ATHLETES_URL = "https://sports.core.api.espn.com/v3/sports/hockey/nhl/athletes"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Fantasy Hockey Draft Board)",
}

# ESPN's player endpoint normally needs this filter to return the complete
# player pool rather than the small browser default.
PLAYER_FILTER = {
    "filterActive": {"value": True},
    "limit": 10000,
    "offset": 0,
}


def _request_json(url: str, *, params: dict[str, Any] | None = None,
                  headers: dict[str, str] | None = None,
                  timeout: int = 30) -> Any:
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

    # Some ESPN responses expose a rankings array rather than the map.
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
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))


def fetch_espn_player_pool() -> list[dict[str, Any]]:
    """Return ESPN-ranked active players, including players ranked below 250."""
    data = _request_json(
        ESPN_PLAYERS_URL,
        params={"view": "players_wl", "scoringPeriodId": 0},
        headers={"X-Fantasy-Filter": __import__("json").dumps({"players": PLAYER_FILTER})},
    )
    rows = data.get("players", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("Unexpected ESPN player response shape")

    output = []
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
            "Status": row.get("status") or player.get("status"),
            "Default Position ID": player.get("defaultPositionId"),
        })

    # ESPN IDs/ranks should be unique. Keep the best-ranked record if a
    # duplicate is returned by the endpoint.
    dedup: dict[str, dict[str, Any]] = {}
    for row in output:
        current = dedup.get(row["Player"])
        if current is None or row["ESPN Ranking"] < current["ESPN Ranking"]:
            dedup[row["Player"]] = row

    return sorted(dedup.values(), key=lambda x: (x["ESPN Ranking"], x["Player"]))


def fetch_espn_ages() -> dict[int, int]:
    """Fetch ESPN's current NHL athlete DOB/age data in one request."""
    data = _request_json(ESPN_ATHLETES_URL, params={"limit": 10000})
    items = data.get("items", []) if isinstance(data, dict) else []
    ages: dict[int, int] = {}
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
        if age is not None:
            try:
                ages[athlete_id] = int(age)
            except (TypeError, ValueError):
                pass
    return ages


def get_espn_rankings() -> list[dict[str, Any]]:
    """Fetch the current ESPN ranked player pool with age metadata."""
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
    for row in rows[:10]:
        print(row)
