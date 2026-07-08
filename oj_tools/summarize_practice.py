"""
复盘总结本次刷题练习。

第一版采用规则分析，不调用网络或模型。它负责解析运行结果、
提取题目关键信息、分析代码特征，并生成结构化的复盘总结。
LLM 可以基于这个总结做进一步翻译和追问。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from oj_tools._algorithm_rules import match_algorithms


# ---------- 复杂度分析规则 ----------

COMPLEXITY_RULES = [
    {
        "time": "O(1)",
        "space": "O(1)",
        "keywords": (),
        "patterns": (),
    },
    {
        "time": "O(log n)",
        "space": "O(1)",
        "keywords": ("二分", "binary search", "bisect", "std::lower_bound", "mid"),
        "patterns": (r"mid\s*=", r"l\s*=\s*mid", r"r\s*=\s*mid"),
    },
    {
        "time": "O(n)",
        "space": "O(1)",
        "keywords": ("双指针", "滑动窗口", "一次遍历", "单循环"),
        "patterns": (),
    },
    {
        "time": "O(n log n)",
        "space": "O(1) 或 O(n)",
        "keywords": ("排序", "sort", "sorted", "std::sort", "Arrays.sort"),
        "patterns": (),
    },
    {
        "time": "O(n²)",
        "space": "O(1) 或 O(n)",
        "keywords": ("暴力", "枚举", "两重循环", "双循环", "双重循环"),
        "patterns": (),
    },
    {
        "time": "O(2ⁿ)",
        "space": "O(n)",
        "keywords": ("回溯", "子集", "组合", "排列", "所有方案", "dfs", "backtrack"),
        "patterns": (r"\bdfs\b", r"\bbacktrack\b", r"\bpermute\b", r"\bcombine\b"),
    },
    {
        "time": "O(V + E)",
        "space": "O(V)",
        "keywords": ("BFS", "DFS", "图", "graph", "queue", "stack", "邻接"),
        "patterns": (r"\.append\(", r"\.pop\(", r"\.popleft\(", r"queue", r"deque"),
    },
]


def _loop_depth(code: str) -> int:
    """推测代码中最大的循环嵌套层数（按 for/while 关键词统计）。"""
    loop_keywords = r"\b(for|while)\b"
    max_depth = 0
    current = 0
    for line in code.splitlines():
        stripped = line.strip()
        if re.search(loop_keywords, stripped):
            current += 1
            max_depth = max(max_depth, current)
        # 空行或纯闭合符（C++/Java的 }）视为一层结束
        if re.match(r"^\s*\}?\s*$", stripped) or stripped == "}":
            current = max(current - 1, 0)
    return max_depth


def _infer_complexity(code: str, problem_text: str) -> dict[str, str]:
    """从代码和题目推测复杂度。"""
    combined = (code + " " + problem_text).lower()
    best = {"time": "未知", "space": "未知"}
    for rule in COMPLEXITY_RULES:
        kw_match = any(kw.lower() in combined for kw in rule["keywords"])
        pt_match = any(re.search(p, code, re.IGNORECASE) for p in rule["patterns"])
        if kw_match or pt_match:
            best = {"time": rule["time"], "space": rule["space"]}
    # 兜底：根据嵌套层数估算
    if best["time"] == "未知":
        depth = _loop_depth(code)
        if depth >= 3:
            best["time"] = f"O(n^{depth})（粗略估算）"
            best["space"] = "O(n)"
        elif depth == 2:
            best["time"] = "O(n²)（粗略估算）"
            best["space"] = "O(n)"
        elif depth == 1:
            best["time"] = "O(n)（粗略估算）"
            best["space"] = "O(1)"
    return best


# ---------- 错误分析 ----------

def _analyze_mistakes(run_result: dict, code: str) -> list[str]:
    """从运行结果中提取用户错误和建议。"""
    mistakes: list[str] = []
    status = run_result.get("status", "")

    if status == "compile_error":
        compile_output = run_result.get("compile_output", "")
        if compile_output:
            mistakes.append(f"编译错误：{compile_output[:200]}")
        else:
            mistakes.append("编译错误：请检查语法、类型声明或缺少分号。")

    elif status == "runtime_error":
        stderr = run_result.get("stderr", "")
        exit_code = run_result.get("exit_code")
        if stderr:
            mistakes.append(f"运行错误：{stderr[:200]}")
        else:
            mistakes.append(f"运行错误：进程退出码 {exit_code}，可能是段错误、越界或栈溢出。")

    elif status == "time_limit_exceeded":
        time_ms = run_result.get("time_ms", 0)
        mistakes.append(f"超时：代码耗时 {time_ms}ms，可能存在死循环或复杂度过高。")
        # 检查常见 TLE 原因
        if _has_unbounded_loop(code):
            mistakes.append("疑似无限循环：检查 while/for 的终止条件。")

    elif status == "wrong_answer":
        diff_info = run_result.get("diff_info", "")
        if diff_info:
            mistakes.append(f"输出错误：{diff_info}")
        else:
            mistakes.append("输出结果与期望不一致，请检查算法逻辑和边界情况。")
        # 常见 WA 原因
        if re.search(r"\bprint\b|\bcout\b|\bSystem\.out\b", code):
            pass  # 至少有输出
        else:
            mistakes.append("代码中可能缺少输出语句？")

    elif status == "accepted":
        pass  # 没有错误

    return mistakes


def _has_unbounded_loop(code: str) -> bool:
    """检查是否有疑似无限循环的模式。"""
    patterns = [
        r"while\s*\(?\s*(true|1)\s*\)?",
        r"while\s*\(\s*\w+\s*\)",  # while(var) 无修改
        r"for\s*\(\s*;;\s*\)",
    ]
    return any(re.search(p, code) for p in patterns)


# ---------- 易错点检测 ----------

COMMON_PITFALLS = [
    {
        "signal": "整数溢出",
        "keywords": ("int", "Integer", "long long", "mod", "1e9"),
        "hint": "注意数据范围，可能需要用 long long 或 Python 的大整数。",
    },
    {
        "signal": "空输入 / 边界",
        "keywords": ("空", "0", "edge", "边界", "空数组", "空串"),
        "hint": "检查 n=0、空字符串、数组为空等边界情况。",
    },
    {
        "signal": "输入格式",
        "keywords": ("scanf", "cin", "input", "split", "多组"),
        "hint": "注意多组测试用例和输入格式（数字间是否有空格、换行）。",
    },
    {
        "signal": "浮点精度",
        "keywords": ("double", "float", "小数", "精度", "eps"),
        "hint": "浮点比较需要用 epsilon 容差，或用整数替代。",
    },
    {
        "signal": "递归深度",
        "keywords": ("recursion", "递归", "dfs", "sys.setrecursionlimit"),
        "hint": "Python 默认递归上限约 1000，大数据可能需要改为迭代或调高限制。",
    },
    {
        "signal": "排序遗漏",
        "keywords": ("Arrays.sort", "vector", "sort", "排序", "有序"),
        "hint": "某些操作（如双指针）依赖有序数据，却忘了先排序。",
    },
]


def _detect_pitfalls(code: str, problem_text: str) -> list[dict[str, str]]:
    """从代码和题目中检测常见易错点。"""
    combined = code.lower() + " " + problem_text.lower()
    pitfalls: list[dict[str, str]] = []
    for pitfall in COMMON_PITFALLS:
        if any(kw.lower() in combined for kw in pitfall["keywords"]):
            pitfalls.append({"易错点": pitfall["signal"], "建议": pitfall["hint"]})
    return pitfalls


# ---------- 下次识别信号 ----------

def _next_recognition_signals(problem_text: str, mistakes: list[str]) -> list[str]:
    """根据题目和本次错误，给出下次见到类似题目的识别信号。"""
    signals: list[str] = []
    lowered = problem_text.lower()

    signal_rules = [
        (("两数之和", "两数", "twosum", "target"), "看到「找两个数满足某条件」→ 优先考虑哈希表或双指针"),
        (("子数组", "子串", "连续", "subarray", "substring"), "看到「连续子数组/子串」→ 考虑滑动窗口或前缀和"),
        (("最短路径", "最少步数", "迷宫", "shortest"), "看到「最短/最少步数」→ 优先 BFS，无权图 BFS 天然最短"),
        (("所有方案", "所有可能", "组合", "排列", "子集"), "看到「所有方案/组合/排列」→ 考虑回溯/DFS"),
        (("最大", "最多", "最长", "最优"), "看到「最大/最优」且存在最优子结构 → 考虑 DP"),
        (("有序", "排序", "sorted"), "看到「有序数组」→ 天然适合二分或双指针"),
        (("区间", "区间合并", "会议室"), "看到「区间重叠/合并」→ 先按起始点排序再处理"),
        (("括号", "匹配", "最近"), "看到「括号/匹配/最近未匹配」→ 用栈"),
        (("前 k", "第 k", "top k", "最小 k"), "看到「前 k 大/小」→ 考虑堆或快速选择"),
        (("连通", "并查集", "union", "朋友圈"), "看到「连通/合并/查询」→ 考虑并查集"),
    ]
    for keywords, signal in signal_rules:
        if any(kw.lower() in lowered for kw in keywords):
            signals.append(signal)

    if not signals:
        signals.append("暂时没有明确识别信号，建议多练习后总结自己的「题感」。")

    return signals


# ---------- 主入口 ----------

def summarize_practice(problem_text: str, code: str, run_result: str, notes: str = "") -> str:
    """复盘总结本次刷题练习，返回结构化 JSON。

    参数:
        problem_text: 题目文本。
        code: 用户提交的代码文本。
        run_result: run_oj_code 返回的 JSON 字符串。
        notes: 用户额外备注（可选）。

    返回 JSON 包含：算法、复杂度、错误、易错点、识别信号。
    """
    if not problem_text.strip():
        return json.dumps({"错误": "problem_text 不能为空"}, ensure_ascii=False)
    if not code.strip():
        return json.dumps({"错误": "code 不能为空"}, ensure_ascii=False)
    if not run_result.strip():
        return json.dumps({"错误": "run_result 不能为空"}, ensure_ascii=False)

    # 解析运行结果
    try:
        parsed_run = json.loads(run_result)
    except json.JSONDecodeError:
        parsed_run = {"status": "unknown", "raw": run_result[:500]}

    status = parsed_run.get("status", "unknown")

    # 提取题目信息
    title = _extract_title(problem_text)
    algorithms = match_algorithms(problem_text)

    # 代码分析
    language = _detect_language(code)
    complexity = _infer_complexity(code, problem_text)

    # 错误与易错点
    mistakes = _analyze_mistakes(parsed_run, code)
    pitfalls = _detect_pitfalls(code, problem_text)
    signals = _next_recognition_signals(problem_text, mistakes)

    result = {
        "题目": title,
        "语言": language,
        "运行状态": status,
        "算法推测": algorithms,
        "时间复杂度": complexity["time"],
        "空间复杂度": complexity["space"],
        "错误分析": mistakes if mistakes else ["未发现错误（AC）"],
        "易错点": pitfalls,
        "下次识别信号": signals,
        "用户备注": notes if notes.strip() else "（未填写）",
        "复盘时间": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------- 辅助函数 ----------

def _extract_title(text: str) -> str:
    """从题目文本中提取标题：首行或首个非空有效行。"""
    for line in text.splitlines():
        cleaned = line.strip().strip("#").strip()
        if cleaned and not cleaned.startswith("```"):
            return cleaned[:120]
    return "未识别到题目标题"


def _detect_language(code: str) -> str:
    """通过代码特征推断编程语言。"""
    if re.search(r"#include\s*<.*>", code) or "int main" in code:
        return "cpp"
    if re.search(r"public\s+class\b|public\s+static\s+void\s+main", code):
        return "java"
    if re.search(r"\bdef\b\s+\w+\s*\(|print\s*\(|import\s+\w+", code):
        return "python"
    return "未知"


def build_summary_memory(summary_json: str) -> str:
    """将复盘总结 JSON 转换为轻量记忆格式（不含完整代码）。

    可用于保存到本地，供后续复盘回顾使用。不默认保存完整代码和敏感信息。
    """
    try:
        summary = json.loads(summary_json)
    except json.JSONDecodeError:
        return json.dumps({"错误": "无法解析 summary_json"}, ensure_ascii=False)

    memory = {
        "题目": summary.get("题目", ""),
        "算法": summary.get("算法推测", []),
        "错误": summary.get("错误分析", []),
        "运行状态": summary.get("运行状态", ""),
        "复盘时间": summary.get("复盘时间", ""),
    }
    return json.dumps(memory, ensure_ascii=False, indent=2)
