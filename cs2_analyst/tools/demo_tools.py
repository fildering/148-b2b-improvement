"""
Demo Parser Tools — ดึงข้อมูลจาก CS2 .dem files
ใช้ demoparser2 (Rust-based, เร็วมาก)
"""

import json
import os
from pathlib import Path

# Try to import demoparser2, fallback to mock data for testing
try:
    from demoparser2 import DemoParser
    HAS_DEMOPARSER = True
except ImportError:
    HAS_DEMOPARSER = False


def parse_demo(file_path: str) -> dict:
    """
    Parse CS2 .dem file และส่งกลับข้อมูลที่ต้องการ
    Returns: dict ที่มี kills, deaths, positions, utility, economy
    """
    if not os.path.exists(file_path):
        return {"error": f"ไม่พบไฟล์: {file_path}"}

    if not HAS_DEMOPARSER:
        return {"error": "ไม่ได้ติดตั้ง demoparser2 — ใช้ mock data แทน"}

    try:
        parser = DemoParser(file_path)

        # ดึง kills events
        kills_df = parser.parse_event("player_death", player=[
            "kills", "deaths", "assists", "headshot_kills",
            "X", "Y", "weapon_name", "total_rounds_played"
        ])

        # ดึง round end events
        rounds_df = parser.parse_event("round_end")

        # ดึง player tick data (positions ทุก tick)
        ticks_df = parser.parse_ticks([
            "X", "Y", "Z", "pitch", "yaw",
            "health", "armor_value",
            "current_equip_value", "total_rounds_played"
        ])

        # ดึง utility events
        utility_df = parser.parse_event("weapon_fire", player=["weapon_name"])

        # summarize
        player_stats = {}
        if kills_df is not None and not kills_df.empty:
            for name, group in kills_df.groupby("attacker_name"):
                player_stats[name] = {
                    "kills": int(group["kills"].sum()) if "kills" in group else len(group),
                    "deaths": int(group["deaths"].sum()) if "deaths" in group else 0,
                    "hs_kills": int(group.get("headshot_kills", 0).sum()) if "headshot_kills" in group.columns else 0,
                }

        return {
            "source": "demo_file",
            "file": Path(file_path).name,
            "player_stats": player_stats,
            "total_rounds": len(rounds_df) if rounds_df is not None else 0,
            "has_position_data": ticks_df is not None and not ticks_df.empty,
        }

    except Exception as e:
        return {"error": f"parse demo ล้มเหลว: {str(e)}"}


def parse_demo_kills(file_path: str) -> dict:
    """
    เน้นดึงข้อมูล kills + headshots + weapons ละเอียด
    """
    if not HAS_DEMOPARSER:
        # Return mock data for development/testing
        return _mock_kill_data()

    try:
        parser = DemoParser(file_path)
        df = parser.parse_event("player_death", player=[
            "X", "Y", "total_rounds_played",
            "flash_duration", "health"
        ])

        kills_list = []
        if df is not None:
            for _, row in df.iterrows():
                kills_list.append({
                    "attacker": row.get("attacker_name", "unknown"),
                    "victim": row.get("user_name", "unknown"),
                    "weapon": row.get("weapon_name", "unknown"),
                    "headshot": bool(row.get("headshot", False)),
                    "round": int(row.get("total_rounds_played", 0)),
                    "pos_x": float(row.get("attacker_X", 0)),
                    "pos_y": float(row.get("attacker_Y", 0)),
                })

        return {"kills": kills_list, "total": len(kills_list)}

    except Exception as e:
        return {"error": str(e)}


def parse_demo_positions(file_path: str, player_name: str) -> dict:
    """
    ดึง position heatmap data สำหรับ player คนนึง
    """
    if not HAS_DEMOPARSER:
        return _mock_position_data(player_name)

    try:
        parser = DemoParser(file_path)
        # ดึงทุก 16 ticks (≈1 วิ) เพื่อลดขนาดข้อมูล
        ticks_df = parser.parse_ticks(["X", "Y", "Z"], player_id=None)

        positions = []
        if ticks_df is not None:
            player_df = ticks_df[ticks_df.get("name", "") == player_name]
            for _, row in player_df.iloc[::16].iterrows():
                positions.append({
                    "x": float(row.get("X", 0)),
                    "y": float(row.get("Y", 0)),
                    "z": float(row.get("Z", 0)),
                })

        return {"player": player_name, "positions": positions, "samples": len(positions)}

    except Exception as e:
        return {"error": str(e)}


def parse_demo_utility(file_path: str) -> dict:
    """
    วิเคราะห์การใช้ utility (grenades, smokes, flashes)
    """
    if not HAS_DEMOPARSER:
        return _mock_utility_data()

    try:
        parser = DemoParser(file_path)

        smoke_df = parser.parse_event("smokegrenade_detonate")
        flash_df = parser.parse_event("flashbang_detonate")
        he_df = parser.parse_event("hegrenade_detonate")
        molotov_df = parser.parse_event("inferno_startburn")

        return {
            "smokes_thrown": len(smoke_df) if smoke_df is not None else 0,
            "flashes_thrown": len(flash_df) if flash_df is not None else 0,
            "he_grenades": len(he_df) if he_df is not None else 0,
            "molotovs": len(molotov_df) if molotov_df is not None else 0,
        }

    except Exception as e:
        return {"error": str(e)}


# ── Mock data สำหรับทดสอบ (ใช้เมื่อไม่มี demoparser2 หรือไม่มีไฟล์ demo) ──

def _mock_kill_data() -> dict:
    return {
        "source": "mock",
        "kills": [
            {"attacker": "PlayerYou", "victim": "Enemy1", "weapon": "ak47", "headshot": True, "round": 1, "pos_x": 512, "pos_y": -1024},
            {"attacker": "PlayerYou", "victim": "Enemy2", "weapon": "ak47", "headshot": False, "round": 1, "pos_x": 300, "pos_y": -800},
            {"attacker": "PlayerYou", "victim": "Enemy3", "weapon": "deagle", "headshot": True, "round": 3, "pos_x": 700, "pos_y": -500},
            {"attacker": "PlayerYou", "victim": "Enemy4", "weapon": "ak47", "headshot": False, "round": 5, "pos_x": 450, "pos_y": -900},
            {"attacker": "PlayerYou", "victim": "Enemy5", "weapon": "m4a4", "headshot": False, "round": 7, "pos_x": 600, "pos_y": -700},
        ],
        "total": 5,
    }


def _mock_position_data(player_name: str) -> dict:
    import random
    positions = [
        {"x": random.uniform(-1500, 1500), "y": random.uniform(-1500, 1500), "z": 0}
        for _ in range(200)
    ]
    return {"player": player_name, "positions": positions, "samples": 200, "source": "mock"}


def _mock_utility_data() -> dict:
    return {
        "source": "mock",
        "smokes_thrown": 8,
        "flashes_thrown": 12,
        "he_grenades": 5,
        "molotovs": 3,
        "utility_per_round": 1.12,
    }
