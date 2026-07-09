"""
ToolRegistry（底盘 · 通常无需修改）
====================================

工具注册表：用装饰器注册普通函数，根据函数签名 + 类型注解 + docstring
自动生成 OpenAI tools 格式的 schema，并按名字调度执行。

>>> registry = ToolRegistry()
>>> @registry.register
... def add(a: int, b: int) -> int:
...     '''把两个整数相加。'''
...     return a + b
"""

from __future__ import annotations

import inspect
from typing import Any, Callable


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable] = {}

    def register(self, func: Callable) -> Callable:
        """装饰器：注册工具函数。"""
        self._tools[func.__name__] = func
        return func

    def to_schemas(self) -> list[dict]:
        """生成 OpenAI tools 格式的 schema 列表。"""
        type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}
        schemas: list[dict] = []
        for name, func in self._tools.items():
            sig = inspect.signature(func)
            hints = getattr(func, "__annotations__", {})
            properties: dict[str, Any] = {}
            required: list[str] = []
            for pname, param in sig.parameters.items():
                if pname == "self":
                    continue
                ann = hints.get(pname, str)
                properties[pname] = {"type": type_map.get(ann, "string")}
                if param.default is inspect.Parameter.empty:
                    required.append(pname)
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": (func.__doc__ or "").strip(),
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required,
                        },
                    },
                }
            )
        return schemas

    def invoke(self, name: str, args: dict) -> str:
        """按名字执行工具，返回字符串结果。"""
        if name not in self._tools:
            return f"❌ 错误：未找到工具 {name}"
        try:
            result = self._tools[name](**args)
            return str(result)
        except Exception as e:
            return f"❌ 工具执行错误: {e}"

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())
