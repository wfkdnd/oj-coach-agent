"""
my-agent 接口定义
=================

所有模块的接口在这里定义。每章实现对应的类，最终第6章组装。
这个文件不需要改动，只是接口参考。
"""

from __future__ import annotations

from typing import Generator, Any, Callable


# ============================================================
# 第1章: LLMClient
# ============================================================
class BaseLLMClient:
    """LLM 客户端接口。"""

    def chat(self, messages: list[dict], **kwargs) -> str:
        """非流式调用，返回完整回复文本。"""
        raise NotImplementedError

    def chat_stream(self, messages: list[dict], **kwargs) -> Generator[str, None, None]:
        """流式调用，逐 chunk yield 文本片段。"""
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        """统计文本的 token 数。"""
        raise NotImplementedError


# ============================================================
# 第2章: ToolRegistry
# ============================================================
class BaseToolRegistry:
    """工具注册表接口。"""

    def register(self, func: Callable) -> Callable:
        """装饰器：注册一个工具函数。"""
        raise NotImplementedError

    def to_schemas(self) -> list[dict]:
        """生成 OpenAI tools 格式的 schema 列表。"""
        raise NotImplementedError

    def invoke(self, name: str, args: dict) -> str:
        """按名字执行工具，返回结果字符串。"""
        raise NotImplementedError


# ============================================================
# 第3章: Agent
# ============================================================
class BaseAgent:
    """Agent 主循环接口。"""

    def __init__(self, llm: BaseLLMClient, tools: BaseToolRegistry, system_prompt: str = ""):
        raise NotImplementedError

    def run(self, user_message: str, max_iterations: int = 10) -> str:
        """执行一个任务，返回最终回答。"""
        raise NotImplementedError


# ============================================================
# 第4章: ContextManager + Memory
# ============================================================
class BaseContextManager:
    """上下文管理器接口。"""

    def should_compress(self, messages: list[dict]) -> bool:
        """判断是否需要压缩。"""
        raise NotImplementedError

    def compress(self, messages: list[dict]) -> list[dict]:
        """压缩 messages，返回新的（更短的）列表。"""
        raise NotImplementedError


class BaseMemory:
    """向量记忆接口。"""

    def add(self, text: str) -> None:
        """存入一条记忆。"""
        raise NotImplementedError

    def search(self, query: str, k: int = 3) -> list[tuple[float, str]]:
        """检索最相关的 k 条记忆，返回 [(similarity, text), ...]。"""
        raise NotImplementedError
