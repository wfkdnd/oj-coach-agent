"""
Agent 主循环

核心逻辑：Agent = LLM + Tools + Loop
"""

from __future__ import annotations

import json

from llm import LLMClient
from tools import ToolRegistry


class Agent:
    def __init__(self, llm: LLMClient, tools: ToolRegistry, system_prompt: str = "你是一个有用的助手。"):
        self.llm = llm
        self.tools = tools
        self.system_prompt = system_prompt

    def run(self, user_message: str, max_iterations: int = 10) -> str:
        """执行任务：循环调用 LLM，有 tool_calls 就执行，没有就返回最终回答。"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]
        tools = self.tools.to_schemas()

        for _ in range(max_iterations):
            resp = self.llm.client.chat.completions.create(
                model=self.llm.model,
                messages=messages, 
                tools=tools, 
                stream=True,
            ) 
            content_parts = []
            tool_calls_map = {}
            for chunk in resp:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    content_parts.append(delta.content)
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_map:
                            tool_calls_map[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc_delta.id:
                            tool_calls_map[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_map[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_map[idx]["arguments"] += tc_delta.function.arguments

            content = "".join(content_parts) if content_parts else None
            tool_calls = [
                {
                    "id": tool_calls_map[i]["id"],
                    "type": "function",
                    "function": {
                        "name": tool_calls_map[i]["name"],
                        "arguments": tool_calls_map[i]["arguments"],
                    },
                }
                for i in sorted(tool_calls_map)
            ] if tool_calls_map else []

            if not tool_calls:
                return content or ""

            # 记录 assistant 的工具调用请求
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls,
            })

            # 执行每个工具并追加结果
            for tc in tool_calls:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError as e:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": f"❌ JSON 解析失败: {e}\n原始参数: {tc['function']['arguments']}",
                    })
                    continue
                result = self.tools.invoke(name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result),
                })

        return "达到最大迭代次数，任务未完成。"
