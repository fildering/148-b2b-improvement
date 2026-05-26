"""
Base Agent — โครงสร้างพื้นฐานของทุก agent
ใช้ Claude API พร้อม tool use
"""

import json
import os
from typing import Any
import anthropic

MODEL = "claude-opus-4-7"
MAX_TOKENS = 4096


class BaseAgent:
    def __init__(self, name: str, system_prompt: str, tools: list[dict]):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.message_history: list[dict] = []

    def run(self, user_message: str, tool_executor: "ToolExecutor | None" = None) -> str:
        """
        รัน agent ด้วย agentic loop
        วนซ้ำจนกว่า Claude จะหยุดเรียก tools
        """
        self.message_history.append({"role": "user", "content": user_message})

        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self.system_prompt,
                tools=self.tools if self.tools else [],
                messages=self.message_history,
            )

            # เก็บ response ลง history
            self.message_history.append({
                "role": "assistant",
                "content": response.content,
            })

            # ถ้าหยุดแล้ว (end_turn หรือ max_tokens) ให้ส่งผลลัพธ์
            if response.stop_reason == "end_turn":
                return self._extract_text(response.content)

            # ถ้ายังมี tool calls ให้รัน
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block, tool_executor)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })

                self.message_history.append({
                    "role": "user",
                    "content": tool_results,
                })
            else:
                # stop_reason อื่นๆ
                return self._extract_text(response.content)

    def _execute_tool(self, tool_use_block, tool_executor) -> Any:
        """รัน tool จาก block ที่ Claude ขอ"""
        tool_name = tool_use_block.name
        tool_input = tool_use_block.input

        if tool_executor:
            return tool_executor.execute(tool_name, tool_input)

        return {"error": f"ไม่มี executor สำหรับ tool: {tool_name}"}

    def reset(self):
        """เคลียร์ประวัติ conversation"""
        self.message_history = []

    @staticmethod
    def _extract_text(content: list) -> str:
        """ดึง text จาก response content"""
        parts = []
        for block in content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts)


class ToolExecutor:
    """Registry สำหรับ tools ที่ agents จะเรียกใช้"""

    def __init__(self):
        self._registry: dict[str, callable] = {}

    def register(self, name: str, func: callable):
        self._registry[name] = func

    def execute(self, name: str, inputs: dict) -> Any:
        if name not in self._registry:
            return {"error": f"ไม่พบ tool: {name}"}
        try:
            return self._registry[name](**inputs)
        except Exception as e:
            return {"error": f"Tool {name} error: {str(e)}"}
