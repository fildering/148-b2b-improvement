"""
Comparison Agent — เปรียบเทียบ stats ของเรากับ pro / benchmark
"""

from agents.base_agent import BaseAgent, ToolExecutor
from tools import stats_tools

SYSTEM_PROMPT = """คุณเป็น CS2 Performance Comparison Agent

หน้าที่: เปรียบเทียบ performance ของผู้เล่นกับ benchmark หรือ pro player

วิธีเปรียบเทียบ:
1. เทียบ K/D, HS%, ADR, Win Rate กับ benchmark level ที่เหมาะสม
2. ให้ rating แต่ละ metric (S/A/B/C/D)
3. ระบุจุดแข็ง (เหนือกว่า benchmark ≥10%) และจุดอ่อน (ต่ำกว่า ≥15%)
4. Overall rating สรุปภาพรวม

ตอบด้วยการเปรียบเทียบที่ชัดเจน มีตัวเลข และกระตุ้นให้พัฒนา
"""

TOOLS = [
    {
        "name": "compare_stats",
        "description": "เปรียบเทียบ stats ของผู้เล่นกับ reference stats",
        "input_schema": {
            "type": "object",
            "properties": {
                "your_stats": {
                    "type": "object",
                    "description": "Stats ของผู้เล่น (kd_ratio, headshots_pct, win_rate, avg_kills, adr)",
                },
                "reference_stats": {
                    "type": "object",
                    "description": "Stats ของ reference player หรือ benchmark",
                },
                "label": {
                    "type": "string",
                    "description": "ชื่อ reference เช่น 'Pro', 'Faceit10', 'Target'",
                    "default": "Benchmark",
                },
            },
            "required": ["your_stats", "reference_stats"],
        },
    },
    {
        "name": "get_benchmark_stats",
        "description": "ดึง benchmark stats สำหรับ level ที่ต้องการ",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "description": "Level: faceit_5, faceit_7, faceit_10, pro",
                    "enum": ["faceit_5", "faceit_7", "faceit_10", "pro"],
                }
            },
            "required": ["level"],
        },
    },
    {
        "name": "identify_improvement_areas",
        "description": "ระบุจุดที่ต้องพัฒนาจาก comparison result",
        "input_schema": {
            "type": "object",
            "properties": {
                "comparison_result": {
                    "type": "object",
                    "description": "Output จาก compare_stats tool",
                }
            },
            "required": ["comparison_result"],
        },
    },
]


def build_executor() -> ToolExecutor:
    executor = ToolExecutor()
    executor.register("compare_stats", stats_tools.compare_stats)
    executor.register("get_benchmark_stats", stats_tools.get_benchmark_stats)
    executor.register("identify_improvement_areas", stats_tools.identify_improvement_areas)
    return executor


class ComparisonAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ComparisonAgent",
            system_prompt=SYSTEM_PROMPT,
            tools=TOOLS,
        )
        self.executor = build_executor()

    def compare(self, your_stats: dict, target_level: str = "faceit_10",
                reference_stats: dict | None = None, reference_label: str = "Pro") -> str:
        """
        เปรียบเทียบกับ benchmark หรือ pro stats
        """
        import json
        ref_info = ""
        if reference_stats:
            ref_info = f"Pro/Reference stats: {json.dumps(reference_stats, ensure_ascii=False)}"
        else:
            ref_info = f"เปรียบเทียบกับ benchmark level: {target_level}"

        prompt = f"""
เปรียบเทียบ performance ต่อไปนี้:

Stats ของผู้เล่น:
{json.dumps(your_stats, ensure_ascii=False, indent=2)}

{ref_info}

กรุณา:
1. ดึง benchmark stats ของ level {target_level}
2. เปรียบเทียบแต่ละ metric
3. ระบุจุดแข็งและจุดอ่อน
4. ให้ overall rating
"""
        return self.run(prompt, self.executor)
