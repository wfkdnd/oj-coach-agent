"""
对比 OJ 代码实际输出与期望输出。

第一版至少忽略末尾空白和换行差异，后续可扩展：
- 忽略多余空格
- 浮点误差容忍
- 仅比较关键行
"""

from __future__ import annotations

import json
import re


COMPARE_MODES = {"strict", "trailing", "relaxed", "full_trim"}


def compare_output(
    stdout: str = "",
    expected_output: str = "",
    mode: str = "trailing",
) -> str:
    """对比实际输出与期望输出，返回结构化 JSON 结果。

    mode:
      - "strict"：完全逐字符对比。
      - "trailing"（默认）：忽略每行末尾空白和末尾空行。
      - "relaxed"：合并连续空白后再对比。
      - "full_trim"：去掉每行首尾空白和首尾空行后再对比。
    """
    if mode not in COMPARE_MODES:
        return json.dumps(
            {
                "status": "error",
                "message": f"不支持的对比模式 '{mode}'，可选：{', '.join(sorted(COMPARE_MODES))}",
            },
            ensure_ascii=False,
            indent=2,
        )

    expected_exists = bool(expected_output.strip())
    if not expected_exists:
        return json.dumps(
            {
                "status": "no_expected_output",
                "normalized_stdout": _normalize(stdout, mode),
                "normalized_expected": "",
                "matched": None,
                "diff_info": "未提供期望输出，无法判断对错。",
            },
            ensure_ascii=False,
            indent=2,
        )

    normalized_stdout = _normalize(stdout, mode)
    normalized_expected = _normalize(expected_output, mode)

    if normalized_stdout == normalized_expected:
        return json.dumps(
            {
                "status": "accepted",
                "normalized_stdout": normalized_stdout,
                "normalized_expected": normalized_expected,
                "matched": True,
                "diff_info": "",
            },
            ensure_ascii=False,
            indent=2,
        )

    diff_info = _describe_diff(normalized_stdout, normalized_expected)
    return json.dumps(
        {
            "status": "wrong_answer",
            "normalized_stdout": normalized_stdout,
            "normalized_expected": normalized_expected,
            "matched": False,
            "diff_info": diff_info,
        },
        ensure_ascii=False,
        indent=2,
    )


def _normalize(text: str, mode: str) -> str:
    """按指定模式标准化文本。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if mode == "trailing":
        text = _strip_trailing(text)
    elif mode == "relaxed":
        text = _collapse_whitespace(text)
    elif mode == "full_trim":
        text = _full_trim(text)
    return text


def _strip_trailing(text: str) -> str:
    """去掉每行末尾空白，并去掉首尾空行。"""
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _collapse_whitespace(text: str) -> str:
    """将连续空白合并为单个空格。"""
    return "\n".join(
        re.sub(r"[ \t]+", " ", line.rstrip()).strip()
        for line in text.splitlines()
    )


def _full_trim(text: str) -> str:
    """去掉每行首尾空白，并去掉首尾空行。"""
    lines = [line.strip() for line in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _describe_diff(stdout: str, expected: str) -> str:
    """生成差异描述，帮助 LLM 解释错误。"""
    stdout_lines = stdout.splitlines()
    expected_lines = expected.splitlines()
    parts: list[str] = []

    min_lines = min(len(stdout_lines), len(expected_lines))
    first_diff = None
    for idx in range(min_lines):
        if stdout_lines[idx] != expected_lines[idx]:
            first_diff = idx + 1  # 1-based
            parts.append(
                f"第 {first_diff} 行不一致：\n"
                f"  期望: {expected_lines[idx]}\n"
                f"  实际: {stdout_lines[idx]}"
            )
            break

    if first_diff is None:
        longer = "期望输出" if len(expected_lines) > len(stdout_lines) else "实际输出"
        shorter = "实际输出" if len(expected_lines) > len(stdout_lines) else "期望输出"
        if len(expected_lines) != len(stdout_lines):
            parts.append(
                f"行数不一致：{shorter} {min(len(stdout_lines), len(expected_lines))} 行，"
                f"{longer} {max(len(stdout_lines), len(expected_lines))} 行。"
            )

    if not parts:
        parts.append("输出内容不一致，但首次差异不在行内。")

    return "；".join(parts)
