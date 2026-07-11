"""测试可复用的 OJCoachSession 工作流层。"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oj_coach import OJCoachSession


PROBLEM = """## A+B
给定两个整数 a 和 b，输出它们的和。

样例输入：
1 2

样例输出：
3
"""

PYTHON_AC_CODE = "a, b = map(int, input().split())\nprint(a + b)"


def _make_session(auto_run=True):
    return OJCoachSession(llm_factory=lambda: None, auto_run=auto_run)


def test_set_problem_text_falls_back_to_rule_cases():
    session = _make_session()

    result = session.set_problem_text(PROBLEM)
    status = session.status()

    assert result["ok"] is True
    assert status["problem_text_set"] is True
    assert status["analysis_result_set"] is True
    assert status["runnable_case_count"] == 1
    assert status["test_case_sources"] == {"题目": 1}


def test_set_code_auto_runs_existing_problem_case():
    session = _make_session()
    session.set_problem_text(PROBLEM)

    result = session.set_code(PYTHON_AC_CODE, "python")
    run_result = json.loads(result["run_result"])

    assert result["ok"] is True
    assert run_result["status"] == "accepted"
    assert run_result["case_count"] == 1
    assert run_result["passed_count"] == 1
    assert session.status()["last_run_result_set"] is True


def test_add_cases_and_run_code_without_auto_run():
    session = _make_session(auto_run=False)
    session.set_code(PYTHON_AC_CODE, "python")

    add_result = session.add_cases("输入：\n5 7\n输出：\n12")
    run_result = session.run_code()
    parsed = json.loads(run_result["run_result"])

    assert add_result["ok"] is True
    assert run_result["ok"] is True
    assert parsed["status"] == "accepted"
    assert parsed["case_count"] == 1


def test_summary_rule_version_without_llm():
    session = _make_session()
    session.set_problem_text(PROBLEM)
    session.set_code(PYTHON_AC_CODE, "python")

    result = session.summarize("测试通过")
    summary = json.loads(result["rule_summary"])

    assert result["ok"] is True
    assert result["llm_summary"] == ""
    assert summary["运行状态"] == "accepted"
    assert summary["用户备注"] == "测试通过"


def test_ask_reports_missing_llm():
    session = _make_session()

    result = session.ask("这题怎么做？")

    assert result["ok"] is False
    assert any("LLM" in message for message in result["messages"])


def test_build_question_context_uses_context_provider_when_available():
    session = OJCoachSession(
        llm_factory=lambda: None,
        context_provider=lambda question: f"压缩上下文：{question}",
    )

    assert session.build_question_context("这题怎么想？") == "压缩上下文：这题怎么想？"


def test_build_question_context_falls_back_when_context_provider_empty():
    session = OJCoachSession(
        llm_factory=lambda: None,
        context_provider=lambda question: "",
    )
    session.state.code = "print(1)"

    context = session.build_question_context("这题怎么想？")

    assert "用户问题" in context
    assert "print(1)" in context
