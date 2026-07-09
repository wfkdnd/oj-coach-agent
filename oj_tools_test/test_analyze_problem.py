"""第7章 测试：analyze_problem — 题目分析"""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_tools.analyze_problem import analyze_problem, extract_problem_test_cases


SIMPLE_PROBLEM = """## 两数之和
给定一个整数数组 nums 和一个整数目标值 target，请你在该数组中找出和为目标值的那两个整数，并返回它们的数组下标。

输入：
第一行包含两个整数 n 和 target。
第二行包含 n 个整数。

输出：
输出两个整数下标，空格分隔。

约束：
2 <= n <= 10000
-1e9 <= nums[i] <= 1e9

样例输入：
4 9
2 7 11 15

样例输出：
0 1
"""

PROBLEM_WITH_SECTIONS = """题目描述：
给一个长度为 n 的整数数组，求连续子数组的最大和。

输入描述：
第一行包含一个整数 n（1 <= n <= 100000）。
第二行包含 n 个整数。

输出描述：
输出一个整数，表示最大子数组和。

Constraints:
-1000 <= nums[i] <= 1000

示例输入 1：
5
-2 1 -3 4 -1

示例输出 1：
6

示例输入 2：
1
5

示例输出 2：
5
"""


def test_basic_structure():
    """基本结构：返回合法 JSON，包含必要字段"""
    result = analyze_problem(SIMPLE_PROBLEM)
    data = json.loads(result)
    assert "标题" in data, f"应该有标题字段，实际 keys: {list(data.keys())}"
    assert "题意" in data
    assert "输入描述" in data
    assert "输出描述" in data
    assert "约束" in data
    assert "样例" in data
    assert "测试用例" in data
    assert "算法候选" in data
    assert "学习建议" in data


def test_title_extraction():
    """提取标题（去除 Markdown # 前缀）"""
    result = analyze_problem(SIMPLE_PROBLEM)
    data = json.loads(result)
    assert "两数之和" in data["标题"], f"标题应包含'两数之和'，实际: {data['标题']}"


def test_constraint_extraction():
    """提取约束：n 的范围"""
    result = analyze_problem(SIMPLE_PROBLEM)
    data = json.loads(result)
    constraints = data["约束"]
    assert len(constraints) >= 2, f"至少应找到 2 条约束，实际: {constraints}"
    assert any("n" in c and "10000" in c for c in constraints), "应找到 n <= 10000"
    assert any("1e9" in c.replace(" ","") or "1000000000" in c for c in constraints), \
        "应找到 nums[i] 的约束"


def test_sample_extraction():
    """提取样例输入/输出"""
    result = analyze_problem(SIMPLE_PROBLEM)
    data = json.loads(result)
    samples = data["样例"]
    assert len(samples) >= 1, f"至少应有 1 个样例，实际: {len(samples)}"
    assert "4 9" in samples[0]["输入"], f"样例输入应包含 '4 9'，实际: {samples[0]['输入']}"
    assert "0 1" in samples[0]["输出"], f"样例输出应包含 '0 1'，实际: {samples[0]['输出']}"


def test_test_cases_built_from_samples():
    """测试用例由样例自动生成"""
    result = analyze_problem(SIMPLE_PROBLEM)
    data = json.loads(result)
    test_cases = data["测试用例"]
    assert len(test_cases) >= 1, f"至少应有 1 组测试用例，实际: {len(test_cases)}"
    assert "stdin" in test_cases[0]
    assert "expected_output" in test_cases[0]
    assert "4 9" in test_cases[0]["stdin"]


def test_algorithm_candidates():
    """算法候选：根据关键词匹配"""
    result = analyze_problem(SIMPLE_PROBLEM)
    data = json.loads(result)
    candidates = data["算法候选"]
    assert len(candidates) >= 1, "至少应有 1 个算法候选"
    algo_names = [c["算法"] for c in candidates]
    assert any("哈希" in name for name in algo_names), \
        f"应该匹配到哈希表，实际算法: {algo_names}"


def test_learning_advice():
    """学习建议不应为空"""
    result = analyze_problem(SIMPLE_PROBLEM)
    data = json.loads(result)
    advice = data["学习建议"]
    assert len(advice) >= 1, "学习建议不应为空"


def test_empty_input():
    """空输入应返回错误"""
    result = analyze_problem("")
    assert "错误" in result or "请提供" in result, f"空输入应报错，实际: {result}"


def test_extract_problem_test_cases():
    """extract_problem_test_cases 公共函数"""
    cases = extract_problem_test_cases(SIMPLE_PROBLEM)
    assert len(cases) >= 1, f"至少应有 1 组测试用例，实际: {len(cases)}"
    assert cases[0]["stdin"].strip(), "stdin 不应为空"


def test_multiple_samples():
    """多组样例"""
    result = analyze_problem(PROBLEM_WITH_SECTIONS)
    data = json.loads(result)
    samples = data["样例"]
    assert len(samples) == 2, f"应有 2 组样例，实际: {len(samples)}"
    assert len(data["测试用例"]) == 2, "应有 2 组测试用例"


def test_section_aliases():
    """识别不同命名风格的段落标题"""
    result = analyze_problem(PROBLEM_WITH_SECTIONS)
    data = json.loads(result)
    assert data["题意"].strip(), "应识别'题目描述'为题意"
    assert data["输入描述"].strip(), "应识别'输入描述'"
    assert data["输出描述"].strip(), "应识别'输出描述'"
    assert data["约束"], "应识别 Constraints"


def test_problem_without_matching_keywords():
    """无匹配关键词时应返回兜底算法"""
    result = analyze_problem("这是一个没有明显关键词的问题。输入一个数字，输出它的平方。")
    data = json.loads(result)
    candidates = data["算法候选"]
    assert len(candidates) >= 1
    assert candidates[0]["算法"] == "待进一步判断"


if __name__ == "__main__":
    test_basic_structure()
    print("  [OK] test_basic_structure")
    test_title_extraction()
    print("  [OK] test_title_extraction")
    test_constraint_extraction()
    print("  [OK] test_constraint_extraction")
    test_sample_extraction()
    print("  [OK] test_sample_extraction")
    test_test_cases_built_from_samples()
    print("  [OK] test_test_cases_built_from_samples")
    test_algorithm_candidates()
    print("  [OK] test_algorithm_candidates")
    test_learning_advice()
    print("  [OK] test_learning_advice")
    test_empty_input()
    print("  [OK] test_empty_input")
    test_extract_problem_test_cases()
    print("  [OK] test_extract_problem_test_cases")
    test_multiple_samples()
    print("  [OK] test_multiple_samples")
    test_section_aliases()
    print("  [OK] test_section_aliases")
    test_problem_without_matching_keywords()
    print("  [OK] test_problem_without_matching_keywords")
    print("\n[PASS] 第7章 analyze_problem 全部测试通过")
