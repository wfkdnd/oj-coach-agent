"""
第5章产出：Coding 工具集
=========================

在 coding_tools/ 目录下实现 5 个工具函数，然后在这里统一注册到 ToolRegistry。
"""

from tools import ToolRegistry
from coding_tools.read import read_file
from coding_tools.write import write_file
from coding_tools.edit import edit_file
from coding_tools.list_dir import list_dir
from coding_tools.bash import bash


def build_coding_tools() -> ToolRegistry:
    """构建包含 5 个 Coding 工具的 ToolRegistry。"""
    registry = ToolRegistry()
    registry.register(read_file)
    registry.register(write_file)
    registry.register(edit_file)
    registry.register(list_dir)
    registry.register(bash)
    return registry
