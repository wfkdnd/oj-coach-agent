"""
场景工具（★ 换场景时在这里改 ★）
==================================

这是「注册进 Agent 的工具集」的场景专属槽位。把你这个 Agent 需要的
领域能力，写成一个个普通函数放到本目录，然后在下面的
register_agent_tools() 里注册即可。

写工具函数的约定（ToolRegistry 会据此自动生成 schema）：
  1. 普通函数，用类型注解标注每个参数（str/int/float/bool）
  2. 第一行 docstring 会作为工具的 description（务必写清「做什么/何时用」）
  3. 无默认值的参数视为必填
  4. 返回值转成字符串回灌给模型

删掉下面的示例，换成你自己的工具。
"""

from __future__ import annotations

from ..tools import ToolRegistry
from .example_tool import get_current_time


def register_agent_tools(registry: ToolRegistry) -> ToolRegistry:
    """把本场景的工具注册到给定的 ToolRegistry，并返回它。"""
    registry.register(get_current_time)
    # registry.register(your_tool_here)
    return registry


__all__ = ["register_agent_tools"]
