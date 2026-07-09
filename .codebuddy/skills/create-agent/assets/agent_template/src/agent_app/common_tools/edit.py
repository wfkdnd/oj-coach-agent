"""edit_file 工具。"""

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

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return f"❌ 读取失败: {e}"

    count = content.count(old_content)
    if count == 0:
        return "❌ 未找到要替换的内容，请检查 old_content 是否与原文完全一致"
    if count > 1:
        return f"❌ old_content 匹配到 {count} 处，必须唯一。请提供更多上下文"

    new_text = content.replace(old_content, new_content)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_text)
    except Exception as e:
        return f"❌ 写入失败: {e}"

    return f"✅ 已成功编辑: {file_path}"
