"""list_dir 工具 — 第5章实现。"""

import os


def list_dir(path: str = ".") -> str:
    """列出目录内容，返回格式化的文件列表。

    Args:
        path: 目录路径
    """
 
    if not os.path.isdir(path):
        return f"❌ 不是目录: {path}"
    
    files = os.listdir(path)
    files.sort()
    return "\n".join(f"[{'文件' if os.path.isfile(os.path.join(path, file)) else '目录'}] {file}" for file in files)
