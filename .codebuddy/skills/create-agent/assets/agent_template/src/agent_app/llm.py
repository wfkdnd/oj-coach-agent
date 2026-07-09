"""
LLMClient（底盘 · 通常无需修改）
=================================

对 OpenAI 兼容接口的轻封装。依赖环境变量：
  - BASE_URL / API_KEY / MODEL_ID          （本地 .env）
  - 或 CNB_API_ENDPOINT / CNB_REPO_SLUG / CNB_TOKEN （CNB 云端自动注入）

注意：部分平台接口仅支持流式输出（stream=True），
因此所有调用内部强制流式，再拼接为完整结果返回，模拟非流式行为。
"""

from __future__ import annotations

import os
from typing import Callable, Generator, List, Optional

import tiktoken
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()


# ============================================================
# 数据类：用 pydantic 模拟 OpenAI 非流式响应的 message 结构。
# 用 BaseModel 而非普通类，使 msg 可被 SDK 自动序列化。
# ============================================================

class Function(BaseModel):
    """tool_call.function"""
    name: str
    arguments: str


class ToolCall(BaseModel):
    """单个 tool_call"""
    id: str
    type: str = "function"
    function: Function


class Message(BaseModel):
    """模拟 ChatCompletionMessage"""
    role: str = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class LLMClient:
    def __init__(self):
        # 本地优先用 .env 的 BASE_URL；云端用 CNB 自动注入的环境变量拼接
        base_url = os.environ.get("BASE_URL")
        if not base_url:
            endpoint = os.environ.get("CNB_API_ENDPOINT", "https://api.cnb.cool")
            repo_slug = os.environ.get("CNB_REPO_SLUG", "")
            base_url = f"{endpoint}/{repo_slug}/-/ai-ide/v2"

        api_key = os.environ.get("API_KEY") or os.environ.get("CNB_TOKEN", "sk-placeholder")

        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=60.0)
        self.model = os.environ.get("MODEL_ID", "deepseek-v4-flash")
        self.enc = tiktoken.get_encoding("cl100k_base")

    def chat(self, messages: list[dict], **kwargs) -> str:
        """调用 LLM，返回完整回复文本（内部强制流式收集）。"""
        msg = self.complete(messages, **kwargs)
        return msg.content or ""

    def complete(self, messages: list[dict], **kwargs) -> Message:
        """调用 LLM，返回完整的 Message 对象（含 tool_calls，内部强制流式收集）。

        额外支持一个非 SDK 参数 `on_delta: Callable[[str], None]`：若提供，
        每收到一个 content 片段就同步回调一次（tool_calls 片段不回调），
        供上层 UI 实现流式打字机效果。
        """
        on_delta: Callable[[str], None] | None = kwargs.pop("on_delta", None)
        kwargs.pop("stream", None)  # 忽略外部传入的 stream，接口只支持流式
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True, **kwargs
        )
        return self._collect_stream(resp, on_delta=on_delta)

    def chat_stream(self, messages: list[dict], **kwargs) -> Generator[str, None, None]:
        """流式调用，逐 chunk yield 文本片段。"""
        kwargs.pop("stream", None)
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True, **kwargs
        )
        for chunk in resp:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @staticmethod
    def _collect_stream(
        response,
        on_delta: Callable[[str], None] | None = None,
    ) -> Message:
        """流式收集所有 chunk，拼装为完整的 Message 对象。"""
        content_parts: list[str] = []
        tool_calls_map: dict[int, dict] = {}

        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                content_parts.append(delta.content)
                if on_delta is not None:
                    try:
                        on_delta(delta.content)
                    except Exception:
                        pass

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

        return Message(
            role="assistant",
            content="".join(content_parts) if content_parts else None,
            tool_calls=[
                ToolCall(
                    id=tool_calls_map[i]["id"],
                    type="function",
                    # arguments 为空时兜底成 "{}"，否则接口会报 invalid parameter value
                    function=Function(
                        name=tool_calls_map[i]["name"],
                        arguments=tool_calls_map[i]["arguments"] or "{}",
                    ),
                )
                for i in sorted(tool_calls_map)
            ] if tool_calls_map else None,
        )

    def count_tokens(self, text: str) -> int:
        """统计文本的 token 数。"""
        if not text:
            return 0
        return len(self.enc.encode(text))
