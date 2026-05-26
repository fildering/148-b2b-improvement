"""
Data Agent — ดึงและรวมข้อมูลจาก demo file + FACEIT API
"""

from agents.base_agent import BaseAgent, ToolExecutor
from tools import demo_tools, faceit_tools

SYSTEM_PROMPT = """คุณเป็น CS2 Data Collection Agent

หน้าที่: ดึงข้อมูล performance จาก demo file และ FACEIT API

สิ่งที่ต้องทำ:
1. ถ้ามี demo file path → parse demo ดึง kills, positions, utility
2. ถ้ามี FACEIT nickname → ดึง lifetime stats และ match history ล่าสุด
3. รวมข้อมูลทั้งหมดเป็น structured format พร้อมส่งต่อ

ตอบเป็นภาษาไทย ให้กระชับและตรงประเด็น
"""

TOOLS = [
    {
        "name": "parse_demo_kills",
        "description": "Parse demo file เพื่อดึงข้อมูล kills ทั้งหมด weapon ที่ใช้ และ headshot",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path ไปยัง .dem file",
                }
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "parse_demo_utility",
        "description": "Parse demo file เพื่อดึงข้อมูลการใช้ utility (smokes, flashes, HE, molotov)",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path ไปยัง .dem file",
                }
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "get_faceit_player",
        "description": "ดึงข้อมูล FACEIT player จาก nickname (ELO, level, player_id)",
        "input_schema": {
            "type": "object",
            "properties": {
                "nickname": {
                    "type": "string",
                    "description": "FACEIT nickname ของ player",
                }
            },
            "required": ["nickname"],
        },
    },
    {
        "name": "get_faceit_stats",
        "description": "ดึง lifetime stats ของ FACEIT player (K/D, win rate, HS%)",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_id": {
                    "type": "string",
                    "description": "FACEIT player ID",
                }
            },
            "required": ["player_id"],
        },
    },
    {
        "name": "get_recent_matches",
        "description": "ดึง match history ล่าสุดของ player",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_id": {
                    "type": "string",
                    "description": "FACEIT player ID",
                },
                "limit": {
                    "type": "integer",
                    "description": "จำนวน matches ที่ต้องการ (default 10)",
                    "default": 10,
                },
            },
            "required": ["player_id"],
        },
    },
]


def build_executor() -> ToolExecutor:
    executor = ToolExecutor()
    executor.register("parse_demo_kills", demo_tools.parse_demo_kills)
    executor.register("parse_demo_utility", demo_tools.parse_demo_utility)
    executor.register("get_faceit_player", faceit_tools.get_player_by_nickname)
    executor.register("get_faceit_stats", faceit_tools.get_player_stats)
    executor.register("get_recent_matches", faceit_tools.get_recent_matches)
    return executor


class DataAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="DataAgent",
            system_prompt=SYSTEM_PROMPT,
            tools=TOOLS,
        )
        self.executor = build_executor()

    def collect(self, nickname: str | None = None, demo_path: str | None = None) -> str:
        """รวบรวมข้อมูลจากทุกแหล่ง"""
        parts = []
        if nickname:
            parts.append(f"FACEIT nickname: {nickname}")
        if demo_path:
            parts.append(f"Demo file: {demo_path}")

        if not parts:
            return "ต้องระบุ nickname หรือ demo_path อย่างใดอย่างหนึ่ง"

        prompt = "กรุณาดึงข้อมูลจาก: " + " | ".join(parts)
        return self.run(prompt, self.executor)
