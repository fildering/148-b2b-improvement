"""
Base Agent — โครงสร้างพื้นฐานของทุก agent
ใช้ Groq API (ฟรี 14,400 req/วัน)
"""

import json
import os
from typing import Any
from groq import Groq

MODEL = "llama-3.3-70b-versatile"
MAX_ITERATIONS = 8   # ป้องกัน infinite loop


class BaseAgent:
    def __init__(self, name: str, system_prompt: str, tools: list[dict]):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.messages: list[dict] = []

    def run(self, user_message: str, tool_executor: "ToolExecutor | None" = None) -> str:
        if not self.messages:
            self.messages.append({"role": "system", "content": self.system_prompt})

        self.messages.append({"role": "user", "content": user_message})

        groq_tools = self._convert_tools() if self.tools else None
        iterations = 0

        while iterations < MAX_ITERATIONS:
            iterations += 1
            kwargs: dict = {
                "model": MODEL,
                "messages": self.messages,
                "temperature": 0.3,
                "max_tokens": 4096,
            }
            if groq_tools:
                kwargs["tools"] = groq_tools
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message

            # เก็บ response ด้วย fields ที่ Groq รับเท่านั้น
            msg_dict: dict = {"role": message.role, "content": message.content or ""}
            if message.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name,
                                     "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ]
            self.messages.append(msg_dict)

            if not message.tool_calls:
                return message.content or ""

            # รัน tool calls
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                result = tool_executor.execute(fn_name, fn_args) if tool_executor else {}

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

        return "หมด iteration — กรุณาลองใหม่"

    def reset(self):
        self.messages = []

    def _convert_tools(self) -> list[dict]:
        result = []
        for tool in self.tools:
            schema = tool.get("input_schema", {})
            result.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": {
                        "type": schema.get("type", "object"),
                        "properties": schema.get("properties", {}),
                        "required": schema.get("required", []),
                    },
                },
            })
        return result


class ToolExecutor:
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
