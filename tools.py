"""
ToolRegistry
"""

from __future__ import annotations

import inspect
import json
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
        schemas = []
        for name, func in self._tools.items():
            sig = inspect.signature(func)
            properties = {}
            required = []
            for param_name, param in sig.parameters.items():
                param_type = param.annotation
                json_type = type_map.get(param_type, "string")
                properties[param_name] = {"type": json_type}
                if param.default is inspect.Parameter.empty:
                    required.append(param_name)
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": func.__doc__ or "",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
            schemas.append(schema)
        return schemas

    def invoke(self, name: str, args: dict) -> str:
        """按名字执行工具，返回字符串结果。"""
        if name not in self._tools:
            return f"未知工具: {name}"
        func = self._tools[name]
        try:
            result = func(**args)
            return str(result)
        except Exception as e:
            return f"执行错误: {e}"

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())
