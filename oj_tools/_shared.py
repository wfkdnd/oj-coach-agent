"""
oj_tools 共享工具函数和常量。

从 session.py / read_code_file.py / run_oj_code.py 中提取的重复代码，
统一维护一处，避免不一致。
"""

# ── 语言别名 ──────────────────────────────────────────

LANGUAGE_ALIASES: dict[str, str] = {
    "py": "python",
    "python": "python",
    "python3": "python",
    "cpp": "cpp",
    "c++": "cpp",
    "cc": "cpp",
    "java": "java",
}


def normalize_language(language: str) -> str:
    """将语言别名统一为标准名称。"""
    return LANGUAGE_ALIASES.get(language.strip().lower(), "")


# ── 测试用例解析辅助 ──────────────────────────────────

def parse_case_heading(line: str) -> tuple[str, str]:
    """解析测试用例标题行，返回 (字段名, 行内值)。"""
    stripped = line.strip().strip("#").strip()
    if "：" in stripped:
        raw_heading, inline_value = stripped.split("：", 1)
    elif ":" in stripped:
        raw_heading, inline_value = stripped.split(":", 1)
    else:
        raw_heading, inline_value = stripped, ""

    heading = raw_heading.strip().lower()
    if heading in {"输入", "stdin", "input"}:
        return "stdin", inline_value.strip()
    if heading in {"输出", "expected", "expected_output", "output"}:
        return "expected_output", inline_value.strip()
    return "", ""


def append_text(existing: str, line: str) -> str:
    """向已有文本追加一行，自动处理首行换行。"""
    if not existing:
        return line
    return f"{existing}\n{line}"
