"""
通用工具集（底盘 · 大多数 Agent 都用得上）
============================================

包含 5 个文件/命令类工具：read_file / write_file / edit_file / list_dir / bash。
若你的场景不需要「读写文件 / 执行命令」的能力，可以：
  - 在 core.py 里不调用 register_common_tools()，或
  - 直接删除本目录。
"""

from ..tools import ToolRegistry
from .bash import bash
from .edit import edit_file
from .list_dir import list_dir
from .read import read_file
from .write import write_file


def register_common_tools(registry: ToolRegistry) -> ToolRegistry:
    """把 5 个通用工具注册到给定的 ToolRegistry，并返回它。"""
    registry.register(read_file)
    registry.register(write_file)
    registry.register(edit_file)
    registry.register(list_dir)
    registry.register(bash)
    return registry


__all__ = [
    "bash",
    "edit_file",
    "list_dir",
    "read_file",
    "register_common_tools",
    "write_file",
]
