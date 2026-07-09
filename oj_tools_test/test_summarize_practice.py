"""第12章 测试：summarize_practice — 复盘总结"""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_tools.summarize_practice import summarize_practice, build_summary_memory


PROBLEM = "## 两数之和\n给定一个整数数组 nums 和一个整数目标值 target，找出和为 target 的两个数的下标。\n约束：2 <= n <= 10000"
CODE = "def solve():\n    n, target = map(int, input().split())\n    nums = list(map(int, input().split()))\n    seen = {}\n    for i, v in enumerate(nums):\n        if target - v in seen:\n            print(seen[target - v], i)\n            return\n        seen[v] = i\n\nsolve()"


def _parse(raw: str) -> dict:
    return json.loads(raw)


def _make_run_result(status: str, **kwargs) -> str:
    base = {"status": status, "stdout": "", "stderr": "", "exit_code": 0, "compile_output": "", "time_ms": 12, "diff_info": ""}
    base.update(kwargs)
    return json.dumps(base)


def test_ac_scenario():
    """AC 场景：无误报、算法正确、复杂度合理"""
    run_result = _make_run_result("accepted")
    result = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result=run_result))
    assert result["运行状态"] == "accepted"
    assert "哈希表" in result["算法推测"], f"应识别哈希表，实际: {result['算法推测']}"
    assert result["错误分析"] == ["未发现错误（AC）"]
    assert result["用户备注"] == "（未填写）"
    assert "复盘时间" in result


def test_wa_scenario():
    """WA 场景：应包含 diff_info 中的错误描述"""
    run_result = _make_run_result("wrong_answer", diff_info="第 1 行不一致：期望: 0 1 / 实际: 0 2")
    result = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result=run_result))
    assert result["运行状态"] == "wrong_answer"
    assert any("0 1" in e for e in result["错误分析"]), f"应包含 diff_info，实际: {result['错误分析']}"


def test_ce_scenario():
    """CE 场景：编译错误"""
    run_result = _make_run_result("compile_error", compile_output="error: expected ';' before 'return'")
    result = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result=run_result))
    assert result["运行状态"] == "compile_error"
    assert any("编译错误" in e for e in result["错误分析"]), f"应有编译错误，实际: {result['错误分析']}"


def test_re_scenario():
    """RE 场景：运行时错误"""
    run_result = _make_run_result("runtime_error", stderr="IndexError: list index out of range", exit_code=1)
    result = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result=run_result))
    assert result["运行状态"] == "runtime_error"
    assert any("IndexError" in e for e in result["错误分析"])


def test_tle_scenario():
    """TLE 场景：超时"""
    run_result = _make_run_result("time_limit_exceeded", time_ms=3500)
    result = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result=run_result))
    assert result["运行状态"] == "time_limit_exceeded"
    assert any("超时" in e for e in result["错误分析"]), f"应有超时提示，实际: {result['错误分析']}"


def test_empty_problem_text():
    """空题目文本"""
    result = _parse(summarize_practice(problem_text="", code=CODE, run_result=_make_run_result("accepted")))
    assert "错误" in result


def test_empty_code():
    """空代码"""
    result = _parse(summarize_practice(problem_text=PROBLEM, code="", run_result=_make_run_result("accepted")))
    assert "错误" in result


def test_empty_run_result():
    """空运行结果"""
    result = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result=""))
    assert "错误" in result


def test_non_json_run_result():
    """非 JSON 运行结果：应降级处理"""
    result = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result="not a json string"))
    assert result["运行状态"] == "unknown", f"非 JSON 应标记 unknown，实际: {result['运行状态']}"


def test_with_notes():
    """带用户备注"""
    run_result = _make_run_result("accepted")
    result = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result=run_result, notes="练习了哈希表"))
    assert result["用户备注"] == "练习了哈希表"


def test_complexity_fields():
    """复杂度字段存在"""
    run_result = _make_run_result("accepted")
    result = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result=run_result))
    assert "时间复杂度" in result, f"应有时间复杂度，实际 keys: {list(result.keys())}"
    assert "空间复杂度" in result
    assert result["时间复杂度"] != "未知", "哈希表代码应能推断复杂度"


def test_language_detection():
    """自动检测语言"""
    run_result = _make_run_result("accepted")
    result = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result=run_result))
    assert result["语言"] == "python", f"应检测为 python，实际: {result['语言']}"


def test_pitfalls_and_signals():
    """易错点和识别信号不应为空"""
    run_result = _make_run_result("accepted")
    result = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result=run_result))
    assert "易错点" in result
    assert "下次识别信号" in result
    assert len(result["下次识别信号"]) >= 1, "应有至少一条识别信号"


def test_build_summary_memory():
    """轻量记忆格式：不含完整代码"""
    run_result = _make_run_result("wrong_answer", diff_info="输出不一致")
    summary = _parse(summarize_practice(problem_text=PROBLEM, code=CODE, run_result=run_result))
    memory = _parse(build_summary_memory(json.dumps(summary, ensure_ascii=False)))
    assert "题目" in memory
    assert "算法" in memory
    assert "错误" in memory
    assert "运行状态" in memory
    assert "复盘时间" in memory
    # 不应包含完整代码
    assert "code" not in memory
    assert "代码" not in memory


def test_build_summary_memory_invalid_input():
    """build_summary_memory 非法输入"""
    result = _parse(build_summary_memory("not json"))
    assert "错误" in result


if __name__ == "__main__":
    test_ac_scenario()
    print("  [OK] test_ac_scenario")
    test_wa_scenario()
    print("  [OK] test_wa_scenario")
    test_ce_scenario()
    print("  [OK] test_ce_scenario")
    test_re_scenario()
    print("  [OK] test_re_scenario")
    test_tle_scenario()
    print("  [OK] test_tle_scenario")
    test_empty_problem_text()
    print("  [OK] test_empty_problem_text")
    test_empty_code()
    print("  [OK] test_empty_code")
    test_empty_run_result()
    print("  [OK] test_empty_run_result")
    test_non_json_run_result()
    print("  [OK] test_non_json_run_result")
    test_with_notes()
    print("  [OK] test_with_notes")
    test_complexity_fields()
    print("  [OK] test_complexity_fields")
    test_language_detection()
    print("  [OK] test_language_detection")
    test_pitfalls_and_signals()
    print("  [OK] test_pitfalls_and_signals")
    test_build_summary_memory()
    print("  [OK] test_build_summary_memory")
    test_build_summary_memory_invalid_input()
    print("  [OK] test_build_summary_memory_invalid_input")
    print("\n[PASS] 第12章 summarize_practice 全部测试通过")
