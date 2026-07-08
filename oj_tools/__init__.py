"""
OJ 专用工具注册入口。

这个包刻意与 coding_tools 分开，避免通用 Coding Agent 和 OJ 陪练工具互相耦合。
"""

from tools import ToolRegistry
from oj_tools.analyze_problem import analyze_problem
from oj_tools.read_code_file import read_code, read_code_file
from oj_tools.read_problem_file import read_problem, read_problem_file


def build_oj_tools() -> ToolRegistry:
    """构建包含当前 OJ 工具的 ToolRegistry。"""
    registry = ToolRegistry()
    registry.register(read_problem)
    registry.register(read_problem_file)
    registry.register(analyze_problem)
    registry.register(read_code)
    registry.register(read_code_file)
    return registry


__all__ = [
    "build_oj_tools",
    "read_problem",
    "read_problem_file",
    "analyze_problem",
    "read_code",
    "read_code_file",
]
