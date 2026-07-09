"""list_dir 工具。"""

import os


def list_dir(path: str = ".") -> str:
    """列出目录内容，返回格式化的文件列表。

    Args:
        path: 目录路径
    """
    if not os.path.isdir(path):
        return f"❌ 不是有效目录: {path}"

    try:
        entries = sorted(os.listdir(path))
    except Exception as e:
        return f"❌ 读取目录失败: {e}"

    if not entries:
        return "(空目录)"

    lines = []
    for name in entries:
        full = os.path.join(path, name)
        tag = "[目录]" if os.path.isdir(full) else "[文件]"
        lines.append(f"{tag} {name}")
    return "\n".join(lines)
