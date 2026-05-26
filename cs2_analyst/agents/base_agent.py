"""
Base Agent — โครงสร้างพื้นฐานของทุก agent
ใช้ Google Gemini API (ฟรี!) แทน Anthropic
"""

import json
import os
from typing import Any
from google import genai
from google.genai import types

MODEL = "gemini-2.0-flash"


class BaseAgent:
    def __init__(self, name: str, system_prompt: str, tools: list[dict]):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.conversation: list = []

    def run(self, user_message: str, tool_executor: "ToolExecutor | None" = None) -> str:
        """
        รัน agent ด้วย agentic loop
        วนซ้ำจนกว่า Gemini จะหยุดเรียก tools
        """
        self.conversation.append(
            types.Content(role="user", parts=[types.Part(text=user_message)])
        )

        # แปลง tool schema จาก Anthropic format → Gemini format
        gemini_tools = self._convert_tools()

        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            tools=gemini_tools,
        )

        while True:
            response = self.client.models.generate_content(
                model=MODEL,
                contents=self.conversation,
                config=config,
            )

            candidate = response.candidates[0]
            content = candidate.content
            self.conversation.append(content)

            # หา function calls
            function_calls = [
                p for p in content.parts
                if p.function_call is not None
            ]

            # ไม่มี function calls → จบแล้ว ส่งข้อความกลับ
            if not function_calls:
                text_parts = [
                    p.text for p in content.parts
                    if hasattr(p, "text") and p.text
                ]
                return "\n".join(text_parts)

            # รัน function calls แล้วส่งผลกลับ
            function_responses = []
            for part in function_calls:
                fc = part.function_call
                result = {}
                if tool_executor:
                    result = tool_executor.execute(fc.name, dict(fc.args))

                function_responses.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": json.dumps(result, ensure_ascii=False)},
                        )
                    )
                )

            # เพิ่ม function results ลง conversation
            self.conversation.append(
                types.Content(role="user", parts=function_responses)
            )

    def reset(self):
        """เคลียร์ประวัติ conversation"""
        self.conversation = []

    def _convert_tools(self) -> list | None:
        """
        แปลง Anthropic tool format → Gemini FunctionDeclaration format
        Anthropic: input_schema → Gemini: parameters
        """
        if not self.tools:
            return None

        declarations = []
        for tool in self.tools:
            schema = tool.get("input_schema", {})
            params = {
                "type": schema.get("type", "object"),
                "properties": {},
            }

            # แปลง properties
            for prop_name, prop_def in schema.get("properties", {}).items():
                converted = {"type": prop_def.get("type", "string")}
                if "description" in prop_def:
                    converted["description"] = prop_def["description"]
                if "enum" in prop_def:
                    converted["enum"] = prop_def["enum"]
                if "default" in prop_def:
                    converted["default"] = prop_def["default"]
                params["properties"][prop_name] = converted

            if "required" in schema:
                params["required"] = schema["required"]

            declarations.append(
                types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    parameters=params,
                )
            )

        return [types.Tool(function_declarations=declarations)]


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
