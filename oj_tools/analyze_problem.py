"""
分析 OJ 题目文本。

第一版采用规则分析，不调用网络或模型。它负责从题面中提取标题、输入输出、
约束、样例，并根据关键词给出可能的算法候选、判断依据和学习建议。
"""

from __future__ import annotations

import json
import re

from oj_tools._algorithm_rules import ALGORITHM_RULES


SECTION_ALIASES = {
    "题意": ("题目描述", "问题描述", "描述", "Description", "Problem"),
    "输入描述": ("输入", "输入描述", "Input"),
    "输出描述": ("输出", "输出描述", "Output"),
    "约束": ("约束", "数据范围", "限制", "Constraints", "Limit"),
    "样例": (
        "样例",
        "示例",
        "样例输入",
        "输入样例",
        "样例输出",
        "输出样例",
        "示例输入",
        "示例输出",
        "Sample",
        "Example",
        "Sample Input",
        "Sample Output",
        "Example Input",
        "Example Output",
    ),
}

def analyze_problem(problem_text: str) -> str:
    """分析题目文本，返回结构化 JSON 字符串。"""
    normalized_text = _normalize_text(problem_text)
    if not normalized_text:
        return "错误：请提供 problem_text。"

    sections = _extract_sections(normalized_text)
    constraints = _extract_constraints(normalized_text, sections)
    samples = _extract_samples(normalized_text)
    input_types = _infer_input_types(normalized_text)
    candidates = _infer_algorithm_candidates(normalized_text)

    result = {
        "标题": _extract_title(normalized_text),
        "题意": sections.get("题意", ""),
        "输入描述": sections.get("输入描述", ""),
        "输出描述": sections.get("输出描述", ""),
        "约束": constraints,
        "样例": samples,
        "测试用例": _build_problem_test_cases(samples),
        "输入类型判断": input_types,
        "算法候选": candidates,
        "学习建议": _build_learning_advice(candidates, constraints),
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


def extract_problem_test_cases(problem_text: str) -> list[dict[str, str]]:
    """从题目文本中提取可直接运行的样例测试用例。"""
    normalized_text = _normalize_text(problem_text)
    if not normalized_text:
        return []
    return _build_problem_test_cases(_extract_samples(normalized_text))


def _build_problem_test_cases(samples: list[dict[str, str]]) -> list[dict[str, str]]:
    test_cases = []
    for index, sample in enumerate(samples, start=1):
        stdin = sample.get("输入", "").strip()
        expected_output = sample.get("输出", "").strip()
        if stdin or expected_output:
            test_cases.append(
                {
                    "名称": f"题目样例 {index}",
                    "来源": "题目样例",
                    "stdin": stdin,
                    "expected_output": expected_output,
                }
            )
    return test_cases


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip().strip("#").strip()
        if cleaned:
            return cleaned[:120]
    return ""


def _extract_sections(text: str) -> dict[str, str]:
    lines = text.splitlines()
    headings: list[tuple[int, str]] = []

    for index, line in enumerate(lines):
        normalized = _normalize_heading(line)
        for section_name, aliases in SECTION_ALIASES.items():
            if any(normalized == _normalize_heading(alias) for alias in aliases):
                headings.append((index, section_name))
                break

    sections: dict[str, str] = {}
    for position, (start_index, section_name) in enumerate(headings):
        end_index = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        content = "\n".join(lines[start_index + 1 : end_index]).strip()
        if content:
            sections[section_name] = content

    if "题意" not in sections:
        sections["题意"] = _guess_problem_description(text)
    return sections


def _normalize_heading(text: str) -> str:
    return text.strip().strip("#:：").strip().lower()


def _guess_problem_description(text: str) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return ""
    if len(paragraphs[0]) <= 120 and len(paragraphs) > 1:
        return paragraphs[1]
    return paragraphs[0]


def _extract_constraints(text: str, sections: dict[str, str]) -> list[str]:
    constraints: list[str] = []
    if sections.get("约束"):
        constraints.extend(_split_meaningful_lines(sections["约束"]))

    patterns = [
        r"\b\d+\s*<=\s*[a-zA-Z_][a-zA-Z0-9_]*\s*<=\s*\d+\b",
        r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*<=\s*\d+\b",
        r"\b\d+\s*[≤<]\s*[a-zA-Z_][a-zA-Z0-9_]*\s*[≤<]\s*\d+\b",
        r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*[≤<]\s*\d+\b",
        r"\b\d+\s*≤\s*[a-zA-Z_][a-zA-Z0-9_]*\s*≤\s*\d+\b",
    ]
    for pattern in patterns:
        constraints.extend(re.findall(pattern, text))

    return _unique_preserve_order(constraints)


def _extract_samples(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    samples: list[dict[str, str]] = []
    current: dict[str, str] = {}
    current_key = ""

    for line in lines:
        heading = _normalize_heading(line)
        if _is_sample_input_heading(heading):
            if current:
                samples.append(current)
            current = {"输入": "", "输出": ""}
            current_key = "输入"
            inline = _extract_inline_after_colon(line)
            if inline:
                current[current_key] = inline
            continue
        if _is_sample_output_heading(heading):
            if not current:
                current = {"输入": "", "输出": ""}
            current_key = "输出"
            inline = _extract_inline_after_colon(line)
            if inline:
                current[current_key] = inline
            continue
        if current_key and _is_known_section_heading(heading):
            current_key = ""
            continue
        if current_key and current:
            current[current_key] = _append_line(current[current_key], line)

    if current:
        samples.append(current)

    return [sample for sample in samples if sample.get("输入") or sample.get("输出")]


def _is_sample_input_heading(heading: str) -> bool:
    return any(marker in heading for marker in ("样例输入", "输入样例", "示例输入", "sample input", "example input", "input example"))


def _is_sample_output_heading(heading: str) -> bool:
    return any(marker in heading for marker in ("样例输出", "输出样例", "示例输出", "sample output", "example output", "output example"))


def _is_known_section_heading(heading: str) -> bool:
    for aliases in SECTION_ALIASES.values():
        if any(heading == _normalize_heading(alias) for alias in aliases):
            return True
    return False


def _extract_inline_after_colon(line: str) -> str:
    if "：" in line:
        return line.split("：", 1)[1].strip()
    if ":" in line:
        return line.split(":", 1)[1].strip()
    return ""


def _append_line(existing: str, line: str) -> str:
    stripped = line.rstrip()
    if not stripped:
        return existing
    if not existing:
        return stripped
    return f"{existing}\n{stripped}"


def _infer_input_types(text: str) -> list[str]:
    rules = [
        ("数组 / 序列", ("数组", "序列", "列表", "array", "numbers", "nums")),
        ("字符串", ("字符串", "子串", "字符", "string", "str")),
        ("矩阵 / 网格", ("矩阵", "网格", "迷宫", "grid", "matrix")),
        ("树", ("二叉树", "树", "根节点", "tree")),
        ("图", ("图", "节点", "边", "graph", "vertex", "edge")),
        ("区间", ("区间", "会议", "interval")),
        ("多组测试", ("多组", "测试用例", "test cases", "t 组")),
    ]
    lowered = text.lower()
    inferred = [name for name, keywords in rules if any(keyword.lower() in lowered for keyword in keywords)]
    return inferred or ["暂未从关键词判断出明确输入类型"]


def _infer_algorithm_candidates(text: str) -> list[dict[str, str]]:
    lowered = text.lower()
    candidates: list[dict[str, str]] = []

    for rule in ALGORITHM_RULES:
        matched = [keyword for keyword in rule["keywords"] if keyword.lower() in lowered]
        if matched:
            candidates.append(
                {
                    "算法": rule["name"],
                    "判断依据": "、".join(matched),
                    "提示": rule["advice"],
                }
            )

    if not candidates:
        candidates.append(
            {
                "算法": "待进一步判断",
                "判断依据": "题面关键词不足",
                "提示": "建议先补充题目约束、样例和输入输出格式，再判断算法方向。",
            }
        )
    return candidates


def _build_learning_advice(candidates: list[dict[str, str]], constraints: list[str]) -> list[str]:
    advice = ["先确认输入规模，再反推可接受的时间复杂度。"]
    if constraints:
        advice.append("约束里出现的 n、m、k 等规模，是选择暴力、二分、DP 或图算法的重要依据。")
    if candidates and candidates[0]["算法"] != "待进一步判断":
        advice.append(f"优先验证“{candidates[0]['算法']}”是否能覆盖样例和边界情况。")
    advice.append("样例过小不能证明算法正确，后续需要补充边界用例。")
    return advice


def _split_meaningful_lines(text: str) -> list[str]:
    return [line.strip(" -\t") for line in text.splitlines() if line.strip(" -\t")]


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    unique_items = []
    for item in items:
        normalized = item.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_items.append(normalized)
    return unique_items
