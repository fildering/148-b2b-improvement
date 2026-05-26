"""
FACEIT API Tools — ดึงข้อมูล match history และ stats
สมัคร API key ฟรีที่ https://developers.faceit.com/
"""

import os
import requests
from typing import Optional

FACEIT_API_BASE = "https://open.faceit.com/data/v4"


def _headers() -> dict:
    api_key = os.environ.get("FACEIT_API_KEY", "")
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def get_player_by_nickname(nickname: str) -> dict:
    """ดึงข้อมูล FACEIT player จาก nickname"""
    if not os.environ.get("FACEIT_API_KEY"):
        return _mock_player_data(nickname)

    url = f"{FACEIT_API_BASE}/players?nickname={nickname}&game=cs2"
    resp = requests.get(url, headers=_headers(), timeout=10)

    if resp.status_code == 404:
        return {"error": f"ไม่พบ player: {nickname}"}
    if resp.status_code != 200:
        return {"error": f"API error: {resp.status_code}"}

    data = resp.json()
    game_stats = data.get("games", {}).get("cs2", {})

    return {
        "player_id": data.get("player_id"),
        "nickname": data.get("nickname"),
        "avatar": data.get("avatar"),
        "country": data.get("country"),
        "elo": game_stats.get("faceit_elo", 0),
        "level": game_stats.get("skill_level", 0),
        "steam_id": data.get("platforms", {}).get("steam", ""),
    }


def get_player_stats(player_id: str, game: str = "cs2") -> dict:
    """ดึง lifetime stats ของ player"""
    if not os.environ.get("FACEIT_API_KEY"):
        return _mock_lifetime_stats()

    url = f"{FACEIT_API_BASE}/players/{player_id}/stats/{game}"
    resp = requests.get(url, headers=_headers(), timeout=10)

    if resp.status_code != 200:
        return {"error": f"API error: {resp.status_code}"}

    data = resp.json()
    lifetime = data.get("lifetime", {})
    segments = data.get("segments", [])

    # Top maps
    top_maps = []
    for seg in segments[:5]:
        top_maps.append({
            "map": seg.get("label", ""),
            "wins": seg.get("stats", {}).get("Wins", "0"),
            "kd": seg.get("stats", {}).get("Average K/D Ratio", "0"),
        })

    return {
        "matches": lifetime.get("Matches", "0"),
        "wins": lifetime.get("Wins", "0"),
        "win_rate": lifetime.get("Win Rate %", "0"),
        "kd_ratio": lifetime.get("Average K/D Ratio", "0"),
        "headshots_pct": lifetime.get("Average Headshots %", "0"),
        "avg_kills": lifetime.get("Average Kills", "0"),
        "avg_deaths": lifetime.get("Average Deaths", "0"),
        "longest_win_streak": lifetime.get("Longest Win Streak", "0"),
        "top_maps": top_maps,
    }


def get_recent_matches(player_id: str, limit: int = 10) -> dict:
    """ดึง match history ล่าสุด"""
    if not os.environ.get("FACEIT_API_KEY"):
        return _mock_recent_matches()

    url = f"{FACEIT_API_BASE}/players/{player_id}/history?game=cs2&limit={limit}"
    resp = requests.get(url, headers=_headers(), timeout=10)

    if resp.status_code != 200:
        return {"error": f"API error: {resp.status_code}"}

    items = resp.json().get("items", [])
    matches = []
    for m in items:
        teams = m.get("teams", {})
        faction1 = teams.get("faction1", {})
        faction2 = teams.get("faction2", {})
        winner = m.get("results", {}).get("winner", "")

        matches.append({
            "match_id": m.get("match_id"),
            "map": m.get("voting", {}).get("map", {}).get("pick", ["unknown"])[0] if m.get("voting") else "unknown",
            "score_t1": m.get("results", {}).get("score", {}).get("faction1", 0),
            "score_t2": m.get("results", {}).get("score", {}).get("faction2", 0),
            "won": faction1.get("nickname") == winner or faction2.get("nickname") == winner,
            "finished_at": m.get("finished_at"),
        })

    return {"matches": matches, "count": len(matches)}


def get_match_stats(match_id: str) -> dict:
    """ดึง stats รายละเอียดของแต่ละ match"""
    if not os.environ.get("FACEIT_API_KEY"):
        return _mock_match_stats(match_id)

    url = f"{FACEIT_API_BASE}/matches/{match_id}/stats"
    resp = requests.get(url, headers=_headers(), timeout=10)

    if resp.status_code != 200:
        return {"error": f"API error: {resp.status_code}"}

    data = resp.json()
    rounds = data.get("rounds", [])
    if not rounds:
        return {"error": "ไม่มีข้อมูล round"}

    round_data = rounds[0]
    teams = round_data.get("teams", [])

    all_players = []
    for team in teams:
        for player in team.get("players", []):
            ps = player.get("player_stats", {})
            all_players.append({
                "nickname": player.get("nickname"),
                "kills": ps.get("Kills", "0"),
                "deaths": ps.get("Deaths", "0"),
                "assists": ps.get("Assists", "0"),
                "kd": ps.get("K/D Ratio", "0"),
                "kr": ps.get("K/R Ratio", "0"),
                "hs_pct": ps.get("Headshots %", "0"),
                "adr": ps.get("ADR", "0"),
                "mvps": ps.get("MVPs", "0"),
                "rating": ps.get("HLTV Rating", "0"),
            })

    return {
        "match_id": match_id,
        "map": round_data.get("round_stats", {}).get("Map", "unknown"),
        "score": round_data.get("round_stats", {}).get("Score", "0 / 0"),
        "players": all_players,
    }


# ── Mock data ──

def _mock_player_data(nickname: str) -> dict:
    return {
        "source": "mock",
        "player_id": "mock-player-001",
        "nickname": nickname,
        "country": "TH",
        "elo": 1850,
        "level": 8,
        "steam_id": "76561190000000000",
    }


def _mock_lifetime_stats() -> dict:
    return {
        "source": "mock",
        "matches": "342",
        "wins": "189",
        "win_rate": "55.26",
        "kd_ratio": "1.12",
        "headshots_pct": "44.2",
        "avg_kills": "19.3",
        "avg_deaths": "17.2",
        "longest_win_streak": "8",
        "top_maps": [
            {"map": "de_mirage", "wins": "45", "kd": "1.25"},
            {"map": "de_inferno", "wins": "38", "kd": "1.18"},
            {"map": "de_dust2", "wins": "32", "kd": "1.05"},
        ],
    }


def _mock_recent_matches() -> dict:
    return {
        "source": "mock",
        "matches": [
            {"match_id": "mock-match-001", "map": "de_mirage", "score_t1": 16, "score_t2": 10, "won": True},
            {"match_id": "mock-match-002", "map": "de_inferno", "score_t1": 13, "score_t2": 16, "won": False},
            {"match_id": "mock-match-003", "map": "de_ancient", "score_t1": 16, "score_t2": 14, "won": True},
            {"match_id": "mock-match-004", "map": "de_dust2", "score_t1": 9, "score_t2": 16, "won": False},
            {"match_id": "mock-match-005", "map": "de_nuke", "score_t1": 16, "score_t2": 8, "won": True},
        ],
        "count": 5,
    }


def _mock_match_stats(match_id: str) -> dict:
    return {
        "source": "mock",
        "match_id": match_id,
        "map": "de_mirage",
        "score": "16 / 10",
        "players": [
            {"nickname": "PlayerYou", "kills": "24", "deaths": "14", "assists": "5",
             "kd": "1.71", "hs_pct": "54", "adr": "98.3", "rating": "1.45"},
            {"nickname": "ProPlayer1", "kills": "28", "deaths": "12", "assists": "7",
             "kd": "2.33", "hs_pct": "62", "adr": "115.2", "rating": "1.89"},
        ],
    }
