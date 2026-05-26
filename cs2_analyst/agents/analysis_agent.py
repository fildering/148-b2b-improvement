"""
Analysis Agent — วิเคราะห์ข้อมูลที่ดึงมา คำนวณ metrics สำคัญ
"""

import json
from agents.base_agent import BaseAgent, ToolExecutor
from tools import stats_tools

SYSTEM_PROMPT = """คุณเป็น CS2 Performance Analysis Agent

หน้าที่: วิเคราะห์ข้อมูล raw stats เพื่อหา patterns และ metrics สำคัญ

สิ่งที่ต้องวิเคราะห์:
1. **Aim Performance**: K/D, HS%, weapon usage patterns
2. **Round Impact**: ADR, impact score, clutch situations
3. **Utility Usage**: smoke/flash efficiency per round
4. **Consistency**: variance ระหว่าง matches

ใช้ tools เพื่อคำนวณแล้วสรุปผลเป็นภาษาไทย ชัดเจน มีตัวเลขสนับสนุน
"""

TOOLS = [
    {
        "name": "calculate_impact_score",
        "description": "คำนวณ impact score จาก kills, deaths, assists, adr, rounds",
        "input_schema": {
            "type": "object",
            "properties": {
                "kills": {"type": "integer"},
                "deaths": {"type": "integer"},
                "assists": {"type": "integer"},
                "adr": {"type": "number"},
                "rounds": {"type": "integer"},
            },
            "required": ["kills", "deaths", "assists", "adr", "rounds"],
        },
    },
    {
        "name": "analyze_weapon_usage",
        "description": "วิเคราะห์ weapon usage patterns จาก kills list",
        "input_schema": {
            "type": "object",
            "properties": {
                "kills": {
                    "type": "array",
                    "description": "List of kill events with weapon and headshot fields",
                    "items": {"type": "object"},
                }
            },
            "required": ["kills"],
        },
    },
    {
        "name": "analyze_round_performance",
        "description": "วิเคราะห์ win/loss patterns จาก match history",
        "input_schema": {
            "type": "object",
            "properties": {
                "match_history": {
                    "type": "array",
                    "items": {"type": "object"},
                }
            },
            "required": ["match_history"],
        },
    },
    {
        "name": "calculate_hs_percentage",
        "description": "คำนวณ headshot percentage",
        "input_schema": {
            "type": "object",
            "properties": {
                "hs_kills": {"type": "integer"},
                "total_kills": {"type": "integer"},
            },
            "required": ["hs_kills", "total_kills"],
        },
    },
]


def build_executor() -> ToolExecutor:
    executor = ToolExecutor()
    executor.register("calculate_impact_score", stats_tools.calculate_impact_score)
    executor.register("analyze_weapon_usage", stats_tools.analyze_weapon_usage)
    executor.register("analyze_round_performance", stats_tools.analyze_round_performance)
    executor.register("calculate_hs_percentage", stats_tools.calculate_hs_percentage)
    return executor


class AnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="AnalysisAgent",
            system_prompt=SYSTEM_PROMPT,
            tools=TOOLS,
        )
        self.executor = build_executor()

    def analyze(self, raw_data: str) -> str:
        """วิเคราะห์ข้อมูลดิบ"""
        prompt = f"""
วิเคราะห์ข้อมูล CS2 performance ต่อไปนี้:

{raw_data}

กรุณา:
1. คำนวณ metrics สำคัญทั้งหมด
2. วิเคราะห์ weapon usage
3. ประเมิน round consistency
4. สรุปจุดแข็งและจุดอ่อน
"""
        return self.run(prompt, self.executor)
