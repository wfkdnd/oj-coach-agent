"""read_file 工具 — 第5章实现。"""

import os


def read_file(file_path: str, offset: int = 1, limit: int | None = None) -> str:
    """读取文件内容，返回带行号的字符串。

    Args:
        file_path: 文件路径
        offset: 起始行号（1-based）
        limit: 最多读几行
    """
    # TODO: 参考 exercises/05 的 ex_5_1.py
    if not os.path.exists(file_path):
        return f"❌ 文件不存在: {file_path}"
    if not os.path.isfile(file_path):
        return f"❌ 不是文件: {file_path}"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return f"❌ 读取失败: {e}"
    
    lines = content.splitlines()
    start = max(0, offset-1)
    end = start + limit if limit else len(lines)
    selected = lines[start:end]
    return "\n".join(f"{offset+i}: {line}" for i, line in enumerate(selected))
