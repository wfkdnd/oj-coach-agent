"""edit_file 工具 — 第5章实现。"""

import os


def edit_file(file_path: str, old_content: str, new_content: str) -> str:
    """精确替换文件中的一段内容。要求 old_content 在文件中唯一匹配。

    Args:
        file_path: 文件路径
        old_content: 要被替换的原文（必须唯一）
        new_content: 替换后的新内容
    """
 
    if not os.path.exists(file_path):
        return f"❌ 文件不存在: {file_path}"
    if os.path.isdir(file_path):
        return f"❌ 不是文件: {file_path}"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return f"❌ 读取失败: {e}"
    
    if old_content not in content:
        return f"❌ 原文不存在: {old_content}"
    if content.count(old_content) != 1:
        return f"❌ 原文不唯一: {old_content}"
    
    new_content = content.replace(old_content, new_content)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return f"✅ 替换成功: {file_path}"
