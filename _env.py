"""Demo 共用：LLM 配置 + 流式客户端封装。

- 优先使用显式的 `BASE_URL` / `API_KEY`；
- 若在 CNB 平台运行（未显式配置），则自动从 `CNB_API_ENDPOINT` + `CNB_REPO_SLUG`
  拼接 Base URL，并使用 `CNB_TOKEN` 作为 API Key。
- `MODEL_ID` 未设置时默认 `glm-5.0`。
- 接口仅支持流式输出，chat() 内部强制 stream=True，
  拼接完整响应后返回 message 对象，模拟非流式行为。
"""

from __future__ import annotations

import os
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ============================================================
# 环境变量读取
# ============================================================

def get_base_url() -> str:
    """获取 LLM API 的 Base URL。"""
    base_url = os.environ.get("BASE_URL")
    if base_url:
        return base_url

    endpoint = os.environ.get("CNB_API_ENDPOINT", "")
    repo_slug = os.environ.get("CNB_REPO_SLUG", "")
    if endpoint and repo_slug:
        return f"{endpoint}/{repo_slug}/-/ai-ide/v2"

    raise EnvironmentError(
        "请设置 BASE_URL，或同时设置 CNB_API_ENDPOINT 和 CNB_REPO_SLUG 环境变量"
    )


def get_api_key() -> str:
    """获取 API Key。优先读取 `API_KEY`，否则读取 `CNB_TOKEN`。"""
    api_key = os.environ.get("API_KEY") or os.environ.get("CNB_TOKEN")
    if not api_key:
        raise EnvironmentError("请设置 API_KEY 或 CNB_TOKEN 环境变量")
    return api_key


def get_model_id() -> str:
    """获取模型 ID，默认 `glm-5.0`。"""
    return os.environ.get("MODEL_ID", "glm-5.0")


def make_client():
    """创建一个 OpenAI 兼容客户端。"""
    from openai import OpenAI

    return OpenAI(
        base_url=get_base_url(),
        api_key=get_api_key(),
        timeout=int(os.environ.get("LLM_TIMEOUT", "60")),
    )


# ============================================================
# 核心方法：模拟非流式响应
# ============================================================

def chat(
    messages: list[dict],
    *,
    temperature: float = 0,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    stream: bool = False,
    client=None,
    model: str | None = None,
) -> "Message":
    """调用 LLM，返回完整的 Message 对象（内部强制流式收集）。

    参数：
        stream: 是否逐字打印 content（打字机效果）。默认 False 静默收集。

    返回值：
        Message 对象，属性：
        - msg.content: str | None  （完整文本）
        - msg.tool_calls: list[ToolCall] | None
          每个 ToolCall 有：tc.id, tc.function.name, tc.function.arguments

    用法：
        # 静默收集（工具调用等中间步骤）
        msg = chat(messages, tools=TOOLS_SCHEMA)

        # 逐字打印（最终回答）
        msg = chat(messages, stream=True)
    """
    if client is None:
        client = make_client()
    if model is None:
        model = get_model_id()

    # 自动将 Message 对象转为 OpenAI API 可接受的字典格式
    normalized_messages = [
        m.to_dict() if isinstance(m, Message) else m for m in messages
    ]

    kwargs: dict = {
        "model": model,
        "messages": normalized_messages,
        "temperature": temperature,
        "stream": True,  # 强制流式（接口限制）
    }
    if tools:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice

    response = client.chat.completions.create(**kwargs)
    return _collect_stream(response, print_content=stream)


# 别名，语义更清晰
chat_stream = lambda messages, **kwargs: chat(messages, stream=True, **kwargs)


# ============================================================
# 内部实现：流式收集
# ============================================================

def _collect_stream(response, print_content: bool = False) -> "Message":
    """流式收集所有 chunk，拼装为完整的 Message 对象。"""
    content_parts: list[str] = []
    tool_calls_map: dict[int, dict] = {}

    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta

        if delta.content:
            content_parts.append(delta.content)
            if print_content:
                print(delta.content, end="", flush=True)

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

    if print_content and content_parts:
        print()  # 换行

    return Message(
        content="".join(content_parts) if content_parts else None,
        tool_calls=[
            ToolCall(
                id=tool_calls_map[i]["id"],
                function=Function(
                    name=tool_calls_map[i]["name"],
                    arguments=tool_calls_map[i]["arguments"],
                ),
            )
            for i in sorted(tool_calls_map)
        ] if tool_calls_map else None,
    )


# ============================================================
# 数据类：模拟 OpenAI 非流式响应的 message 结构
# ============================================================

class Function:
    """tool_call.function"""
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments

    def __repr__(self):
        return f"Function(name={self.name!r}, arguments={self.arguments!r})"


class ToolCall:
    """单个 tool_call"""
    def __init__(self, id: str, function: Function):
        self.id = id
        self.function = function

    def __repr__(self):
        return f"ToolCall(id={self.id!r}, function={self.function!r})"


class Message:
    """模拟 ChatCompletionMessage"""
    def __init__(self, content: Optional[str], tool_calls: Optional[list] = None):
        self.content = content
        self.tool_calls = tool_calls

    def to_dict(self) -> dict:
        """将 Message 转换为 OpenAI API 可接受的标准字典格式。"""
        msg_dict: dict = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in self.tool_calls
            ]
        return msg_dict

    def __repr__(self):
        if self.tool_calls:
            return f"Message(content={self.content!r}, tool_calls={self.tool_calls!r})"
        return f"Message(content={self.content!r})"
