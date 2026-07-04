"""
Thin client for the free public MLB Stats API. No key required.
"""
import requests

BASE = "https://statsapi.mlb.com/api/v1"
BASE_V1_1 = "https://statsapi.mlb.com/api/v1.1"


def get_live_games(date_str: str) -> list[dict]:
    resp = requests.get(f"{BASE}/schedule", params={"sportId": 1, "date": date_str}, timeout=15)
    resp.raise_for_status()
    games = []
    for date_entry in resp.json().get("dates", []):
        for g in date_entry.get("games", []):
            games.append({
                "game_pk": g["gamePk"],
                "abstract_state": g["status"].get("abstractGameState"),
                "home_team": g["teams"]["home"]["team"]["name"],
                "away_team": g["teams"]["away"]["team"]["name"],
            })
    return games


def get_live_feed(game_pk: int) -> dict:
    resp = requests.get(f"{BASE_V1_1}/game/{game_pk}/feed/live", timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_situation(feed_json: dict) -> dict | None:
    """
    Extracts the current inning/outs/base-runner/score situation from a live
    feed. Returns None if the game isn't in a state where this makes sense
    (e.g. between innings with no current play data yet).
    """
    linescore = (feed_json.get("liveData") or {}).get("linescore") or {}
    inning = linescore.get("currentInning")
    inning_state = linescore.get("inningState")  # "Top", "Bottom", "Middle", "End"
    if inning is None or inning_state not in ("Top", "Bottom"):
        return None

    offense = linescore.get("offense") or {}
    second_occupied = "second" in offense  # key present means a runner is on that base

    outs = linescore.get("outs")
    if outs is None:
        return None

    teams_ls = linescore.get("teams") or {}
    home_runs = (teams_ls.get("home") or {}).get("runs", 0)
    away_runs = (teams_ls.get("away") or {}).get("runs", 0)

    if inning_state == "Top":
        batting_score, fielding_score = away_runs, home_runs
    else:
        batting_score, fielding_score = home_runs, away_runs

    all_plays = (feed_json.get("liveData") or {}).get("plays") or {}
    current_play = all_plays.get("currentPlay") or {}
    at_bat_index = (current_play.get("about") or {}).get("atBatIndex")
    batter_name = ((current_play.get("matchup") or {}).get("batter") or {}).get("fullName")

    return {
        "inning": inning,
        "half": inning_state,
        "outs": outs,
        "second_occupied": second_occupied,
        "first_occupied": "first" in offense,
        "third_occupied": "third" in offense,
        "batting_score": batting_score,
        "fielding_score": fielding_score,
        "at_bat_index": at_bat_index,
        "batter_name": batter_name,
    }
