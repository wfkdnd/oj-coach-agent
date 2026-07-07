"""write_file 工具 — 第5章实现。"""

import os


def write_file(file_path: str, content: str, overwrite: bool = False) -> str:
    """写入文件。默认拒绝覆盖已有文件。

    Args:
        file_path: 目标路径
        content: 内容
        overwrite: 是否覆盖
    """
    # TODO: 参考 exercises/05 的 ex_5_2.py
    if os.path.exists(file_path) and not overwrite:
        return f"❌ 文件已存在: {file_path}（如需覆盖请设 overwrite=True）"
    dirname = os.path.dirname(file_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content)
    return f"✅ 写入成功: {file_path}（{len(content)} 字符）"
