"""write_file 工具。"""

import os


def write_file(file_path: str, content: str, overwrite: bool = False) -> str:
    """写入文件。默认拒绝覆盖已有文件。

    Args:
        file_path: 目标路径
        content: 内容
        overwrite: 是否覆盖
    """
    if os.path.exists(file_path) and not overwrite:
        return f"❌ 文件已存在: {file_path}（如需覆盖请传 overwrite=True）"

    try:
        parent = os.path.dirname(file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"❌ 写入失败: {e}"

    return f"✅ 已写入 {len(content)} 字符到: {file_path}"
