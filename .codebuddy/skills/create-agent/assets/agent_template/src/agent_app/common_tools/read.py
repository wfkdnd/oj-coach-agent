"""read_file 工具。"""

import os


def read_file(file_path: str, offset: int = 1, limit: int | None = None) -> str:
    """读取文件内容，返回带行号的字符串。

    Args:
        file_path: 文件路径
        offset: 起始行号（1-based）
        limit: 最多读几行
    """
    if not os.path.exists(file_path):
        return f"❌ 文件不存在: {file_path}"
    if os.path.isdir(file_path):
        return f"❌ 目标是目录而非文件: {file_path}"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return f"❌ 读取失败: {e}"

    start = max(offset, 1) - 1
    end = start + limit if limit is not None else len(lines)
    selected = lines[start:end]

    out = []
    for i, line in enumerate(selected, start=start + 1):
        out.append(f"{i}:{line.rstrip(chr(10))}")
    return "\n".join(out)
